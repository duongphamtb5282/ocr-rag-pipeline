"""LLM Gateway service — unified entry point for all LLM calls."""

from __future__ import annotations

import logging
import time

from app.gateway.adapters.base import LLMProviderAdapter
from app.gateway.adapters.factory import provider_factory
from app.gateway.cache import gateway_cache
from app.gateway.registry import registry
from app.gateway.router import LLMRequest, router
from app.gateway.telemetry import cost_tracker

logger = logging.getLogger(__name__)


def _get_adapter(provider: str) -> LLMProviderAdapter | None:
    """Resolve the adapter for a provider via the factory (one active at a time)."""
    return provider_factory.get_adapter(provider)


async def gateway_call(request: LLMRequest) -> str:
    """Route an LLM call through the gateway with cost tracking, caching, and fallback."""
    start = time.perf_counter()

    # 1. Check cache (tiered: local memory + Redis)
    cached = await gateway_cache.get(request.route_key, request.messages, request.system_prompt)
    if cached is not None:
        cost_tracker.record_call(
            session_id=request.session_id,
            agent=request.agent,
            route_key=request.route_key,
            provider=cached.get("provider", "cache"),
            model=cached.get("model", "cache"),
            tokens_in=cached.get("tokens_in", 0),
            tokens_out=cached.get("tokens_out", 0),
            latency_ms=0,
            success=True,
            cached=True,
        )
        return cached["content"]

    # 2. Resolve route
    route = await router.resolve_route(request)
    adapter = _get_adapter(route.provider)
    if not adapter:
        raise RuntimeError(f"No adapter for provider: {route.provider}")

    # 3. Call LLM
    try:
        response = await adapter.invoke(
            model=route.model,
            messages=[{"role": "system", "content": request.system_prompt}] + request.messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        elapsed = time.perf_counter() - start
        tokens_in = response["usage"].get("input_tokens", 0)
        tokens_out = response["usage"].get("output_tokens", 0)

        # 4. Record telemetry
        cost_tracker.record_call(
            session_id=request.session_id,
            agent=request.agent,
            route_key=request.route_key,
            provider=route.provider,
            model=route.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=elapsed * 1000,
            success=True,
        )
        registry.record_success(route.provider)

        # 5. Cache the response (async)
        cache_data = {
            "content": response["content"],
            "provider": route.provider,
            "model": route.model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
        await gateway_cache.set(request.route_key, request.messages, cache_data, request.system_prompt)

        return response["content"]

    except Exception as e:
        elapsed = time.perf_counter() - start
        registry.record_failure(route.provider)
        cost_tracker.record_call(
            session_id=request.session_id,
            agent=request.agent,
            route_key=request.route_key,
            provider=route.provider,
            model=route.model,
            tokens_in=0,
            tokens_out=0,
            latency_ms=elapsed * 1000,
            success=False,
            error=str(e),
        )
        raise


async def gateway_embed(text: str, model: str = "text-embedding-3-large", dimensions: int = 1536) -> list[float]:
    """Generate embedding via the active provider when it supports embeddings.

    Falls back to a configured embed-capable provider (openai/azure) when the
    active chat provider has no embedding model (e.g. anthropic) — see factory.
    """
    adapter = provider_factory.get_embedding_adapter()
    if not adapter:
        raise RuntimeError("No embedding provider available")
    return await adapter.embed(text, model=model, dimensions=dimensions)
