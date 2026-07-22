"""Gateway response cache — in-memory dict (dev) and Redis (production)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

CACHE_RULES: dict[str, dict] = {
    "doc_classification":  {"ttl_s": 3600, "cost_saved_per_hit": 0.005},
    "form_analysis":       {"ttl_s": 1800, "cost_saved_per_hit": 0.010},
    "semantic_mapping":    {"ttl_s": 600,  "cost_saved_per_hit": 0.002},
    "field_extraction":    {"ttl_s": 0},     # Never cache
    "vision_ocr":          {"ttl_s": 0},     # Never cache
    "embedding":           {"ttl_s": 3600, "cost_saved_per_hit": 0.0001},
}


class GatewayCache:
    """
    Two-tier cache for LLM responses:
    - L1: in-memory dict (fast, no network)
    - L2: Redis (shared across instances, survives restarts)
    """

    def __init__(self):
        self._local: dict[str, dict] = {}
        self._redis = None
        self._redis_available = False

        # Initialize Redis if configured
        if settings.REDIS_URL:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                self._redis_available = True
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis unavailable, using local cache only: {e}")

    def _make_key(self, route_key: str, messages: list, system_prompt: str = "") -> str:
        """Generate deterministic cache key."""
        content = f"{route_key}|{system_prompt}|{json.dumps(messages, sort_keys=True, default=str)}"
        return f"llm_cache:{route_key}:{hashlib.sha256(content.encode()).hexdigest()}"

    def is_cacheable(self, route_key: str) -> bool:
        rule = CACHE_RULES.get(route_key, {})
        return rule.get("ttl_s", 0) > 0

    async def get(self, route_key: str, messages: list, system_prompt: str = "") -> dict | None:
        """Get cached response. Returns None if miss."""
        if not self.is_cacheable(route_key):
            return None

        key = self._make_key(route_key, messages, system_prompt)

        # L1: local memory
        if key in self._local:
            entry = self._local[key]
            if time.monotonic() < entry["expires_at"]:
                logger.debug(f"Cache HIT (local) for {route_key}")
                return entry["data"]
            else:
                del self._local[key]

        # L2: Redis
        if self._redis_available:
            try:
                data = await self._redis.get(key)
                if data:
                    logger.debug(f"Cache HIT (redis) for {route_key}")
                    parsed = json.loads(data)
                    # Also populate local cache
                    self._local[key] = {
                        "data": parsed,
                        "expires_at": time.monotonic() + 60,  # 1 min local TTL
                    }
                    return parsed
            except Exception as e:
                logger.warning(f"Redis cache get failed: {e}")

        return None

    async def set(self, route_key: str, messages: list, data: Any, system_prompt: str = ""):
        """Store response in cache."""
        if not self.is_cacheable(route_key):
            return

        key = self._make_key(route_key, messages, system_prompt)
        ttl = CACHE_RULES[route_key]["ttl_s"]

        # L1: local memory
        self._local[key] = {
            "data": data,
            "expires_at": time.monotonic() + ttl,
        }

        # L2: Redis
        if self._redis_available:
            try:
                await self._redis.setex(key, ttl, json.dumps(data, default=str))
            except Exception as e:
                logger.warning(f"Redis cache set failed: {e}")

    async def invalidate(self, route_key: str | None = None):
        """Invalidate cache for a route (or all routes if None)."""
        if route_key:
            prefix = f"llm_cache:{route_key}:"
            self._local.clear()  # Clear all local on invalidation
            if self._redis_available:
                try:
                    cursor = 0
                    while True:
                        cursor, keys = await self._redis.scan(cursor, match=f"{prefix}*")
                        if keys:
                            await self._redis.delete(*keys)
                        if cursor == 0:
                            break
                except Exception as e:
                    logger.warning(f"Redis cache invalidation failed: {e}")
        else:
            self._local.clear()
            if self._redis_available:
                try:
                    await self._redis.flushdb()
                except Exception as e:
                    logger.warning(f"Redis flush failed: {e}")

    def get_stats(self) -> dict:
        return {
            "local_entries": len(self._local),
            "redis_connected": self._redis_available,
            "cacheable_routes": [k for k, v in CACHE_RULES.items() if v.get("ttl_s", 0) > 0],
        }


gateway_cache = GatewayCache()
