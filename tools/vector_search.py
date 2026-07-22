"""Vector search tool — unified vector DB access for agents.

Canonical location. Wraps the app.vector client for use by agents and services.
"""

from __future__ import annotations

import logging
from typing import Any

from app.vector import vector_db

logger = logging.getLogger(__name__)


class VectorSearchTool:
    """Vector DB access for agents and services."""

    async def search(
        self,
        collection: str,
        vector: list[float],
        limit: int = 10,
        score_threshold: float = 0.0,
        filter_params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """Search a vector collection by embedding similarity."""
        results = await vector_db.search(collection, vector, limit, score_threshold, filter_params)
        return [
            {
                "session_id": r.session_id,
                "doc_type": r.doc_type,
                "extracted_fields": r.extracted_fields,
                "similarity": r.similarity,
                "created_at": r.created_at,
            }
            for r in results
        ]

    async def upsert(self, collection: str, point_id: str, vector: list[float], payload: dict) -> None:
        """Insert or update a vector point."""
        await vector_db.upsert(collection, point_id, vector, payload)

    async def delete(self, collection: str, filter_params: dict[str, Any] | None = None) -> None:
        """Delete points from a collection."""
        await vector_db.delete(collection, filter_params)

    async def create_collection(self, collection: str, vector_size: int = 1536) -> None:
        """Create a new collection."""
        await vector_db.create_collection(collection, vector_size)


vector_search = VectorSearchTool()
