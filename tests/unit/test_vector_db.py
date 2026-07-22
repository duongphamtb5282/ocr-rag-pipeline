"""Tests for in-memory vector database."""

from __future__ import annotations

import pytest

from app.vector import VectorDB


@pytest.mark.asyncio
async def test_upsert_and_search():
    db = VectorDB()
    await db.upsert("documents", "doc1", [1.0, 0.0, 0.0], {"session_id": "s1", "doc_type": "invoice"})
    await db.upsert("documents", "doc2", [0.0, 1.0, 0.0], {"session_id": "s2", "doc_type": "letter"})

    # Search for similar to doc1
    results = await db.search("documents", [1.0, 0.0, 0.0], limit=5, score_threshold=0.5)
    assert len(results) >= 1
    assert results[0].session_id == "s1"


@pytest.mark.asyncio
async def test_search_with_filter():
    db = VectorDB()
    await db.upsert("documents", "doc1", [1.0, 0.0], {"session_id": "s1", "doc_type": "invoice"})
    await db.upsert("documents", "doc2", [0.9, 0.1], {"session_id": "s2", "doc_type": "letter"})

    results = await db.search("documents", [1.0, 0.0], limit=5, score_threshold=0.5, filter_params={"doc_type": "invoice"})
    assert len(results) == 1
    assert results[0].doc_type == "invoice"


@pytest.mark.asyncio
async def test_delete():
    db = VectorDB()
    await db.upsert("documents", "doc1", [1.0, 0.0], {"session_id": "s1"})
    await db.delete("documents", filter_params={"session_id": "s1"})
    results = await db.search("documents", [1.0, 0.0], limit=5)
    assert len(results) == 0
