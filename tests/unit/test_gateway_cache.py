"""Tests for the gateway cache module."""

from __future__ import annotations

import pytest

from app.gateway.cache import GatewayCache


@pytest.mark.asyncio
async def test_cache_miss():
    cache = GatewayCache()
    result = await cache.get("doc_classification", [{"role": "user", "content": "hello"}])
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_and_get():
    cache = GatewayCache()
    messages = [{"role": "user", "content": "classify this"}]
    data = {"content": "invoice", "provider": "openai", "model": "gpt-4o-mini"}

    await cache.set("doc_classification", messages, data)
    result = await cache.get("doc_classification", messages)
    assert result is not None
    assert result["content"] == "invoice"


@pytest.mark.asyncio
async def test_non_cacheable_route():
    cache = GatewayCache()
    assert cache.is_cacheable("doc_classification") is True
    assert cache.is_cacheable("field_extraction") is False
    assert cache.is_cacheable("vision_ocr") is False


@pytest.mark.asyncio
async def test_cache_invalidate():
    cache = GatewayCache()
    messages = [{"role": "user", "content": "test"}]
    await cache.set("doc_classification", messages, {"content": "test"})
    await cache.invalidate("doc_classification")
    result = await cache.get("doc_classification", messages)
    assert result is None


@pytest.mark.asyncio
async def test_cache_stats():
    cache = GatewayCache()
    stats = cache.get_stats()
    assert "cacheable_routes" in stats
    assert "redis_connected" in stats
    assert "local_entries" in stats
