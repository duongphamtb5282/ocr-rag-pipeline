"""Semantic cache — caches LLM responses for idempotent calls.

Wraps the gateway cache with higher-level semantics for
classification, form analysis, and mapping routes.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from app.gateway.cache import GatewayCache

logger = logging.getLogger(__name__)


class SemanticCache:
    """Semantic caching layer for LLM responses.

    Caches idempotent calls (classification, form analysis, semantic mapping)
    with configurable TTL per route type.
    """

    ROUTE_TTL: dict[str, int] = {
        "doc_classification": 3600,     # 1 hour (document types don't change)
        "form_analysis": 86400,          # 24 hours (forms change rarely)
        "semantic_mapping": 3600,        # 1 hour
        "default": 600,                  # 10 minutes
    }

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._gateway_cache = GatewayCache()

    def _make_key(self, route: str, prompt: str, model: str = "") -> str:
        """Generate a deterministic cache key."""
        raw = f"{route}|{model}|{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(self, route: str, prompt: str, model: str = "") -> Any | None:
        """Get a cached response. Returns None on miss."""
        key = self._make_key(route, prompt, model)
        entry = self._cache.get(key)

        if entry is None:
            return None

        ttl = self.ROUTE_TTL.get(route, self.ROUTE_TTL["default"])
        age = datetime.utcnow() - entry["cached_at"]
        if age > timedelta(seconds=ttl):
            del self._cache[key]
            return None

        logger.debug("Cache hit: %s (age: %ds)", route, int(age.total_seconds()))
        return entry["value"]

    async def set(self, route: str, prompt: str, value: Any, model: str = "") -> None:
        """Cache a response."""
        key = self._make_key(route, prompt, model)
        self._cache[key] = {
            "value": value,
            "cached_at": datetime.utcnow(),
            "route": route,
        }

    async def clear(self, route: str | None = None) -> int:
        """Clear cache entries, optionally filtered by route. Returns count cleared."""
        if route is None:
            count = len(self._cache)
            self._cache.clear()
            return count

        keys = [k for k, v in self._cache.items() if v.get("route") == route]
        for k in keys:
            del self._cache[k]
        return len(keys)

    def stats(self) -> dict[str, Any]:
        return {
            "total_entries": len(self._cache),
            "routes": list(set(v.get("route", "unknown") for v in self._cache.values())),
        }


semantic_cache = SemanticCache()
