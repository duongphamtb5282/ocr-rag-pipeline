"""Semantic search endpoint for finding previously processed documents."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.api.v1.schemas import SearchQuery, SearchResult
from app.vector.search import semantic_search

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/search", response_model=list[SearchResult])
async def search_documents(q: str, doc_type: str | None = None, limit: int = 20):
    """Search across processed documents by semantic similarity."""
    results = await semantic_search.search(q, doc_type=doc_type, limit=limit)
    return [
        SearchResult(
            session_id=r["session_id"],
            doc_type=r["doc_type"],
            extracted_fields=r.get("extracted_fields", {}),
            similarity=r.get("similarity", 0.0),
            created_at=r.get("created_at"),
        )
        for r in results
    ]
