"""Tests for vector database backends (memory, Qdrant adapter, pgvector adapter)."""

from __future__ import annotations

import pytest

from app.vector.backends.memory_backend import MemoryBackend


@pytest.mark.asyncio
async def test_memory_upsert_and_search():
    db = MemoryBackend()
    await db.upsert("docs", "doc1", [1.0, 0.0, 0.0], {"session_id": "s1", "doc_type": "invoice"})
    await db.upsert("docs", "doc2", [0.0, 1.0, 0.0], {"session_id": "s2", "doc_type": "letter"})

    results = await db.search("docs", [1.0, 0.0, 0.0], limit=5, score_threshold=0.5)
    assert len(results) >= 1
    assert results[0].session_id == "s1"


@pytest.mark.asyncio
async def test_memory_search_with_filter():
    db = MemoryBackend()
    await db.upsert("docs", "doc1", [1.0, 0.0], {"session_id": "s1", "doc_type": "invoice"})
    await db.upsert("docs", "doc2", [0.9, 0.1], {"session_id": "s2", "doc_type": "letter"})

    results = await db.search("docs", [1.0, 0.0], limit=5, score_threshold=0.5, filter_params={"doc_type": "invoice"})
    assert len(results) == 1
    assert results[0].doc_type == "invoice"


@pytest.mark.asyncio
async def test_memory_delete():
    db = MemoryBackend()
    await db.upsert("docs", "doc1", [1.0, 0.0], {"session_id": "s1"})
    await db.delete("docs", filter_params={"session_id": "s1"})
    results = await db.search("docs", [1.0, 0.0], limit=5)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_memory_collection_info():
    db = MemoryBackend()
    await db.upsert("docs", "doc1", [1.0, 0.0], {"session_id": "s1"})
    info = await db.collection_info("docs")
    assert info["exists"] is True
    assert info["points"] == 1


@pytest.mark.asyncio
async def test_memory_empty_collection():
    db = MemoryBackend()
    results = await db.search("nonexistent", [1.0, 0.0, 0.0])
    assert len(results) == 0


@pytest.mark.asyncio
async def test_memory_create_collection():
    db = MemoryBackend()
    await db.create_collection("new_coll", vector_size=128)
    await db.upsert("new_coll", "p1", [0.5] * 128, {"key": "val"})
    results = await db.search("new_coll", [0.5] * 128, limit=5, score_threshold=0.9)
    assert len(results) == 1
