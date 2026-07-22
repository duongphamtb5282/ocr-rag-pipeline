"""Hybrid retriever — semantic + keyword search across documents.

Wraps the vector DB client and embedding gateway into a unified
retrieval interface for downstream consumers (agents, services).
"""

from __future__ import annotations

import logging
from typing import Any

from app.gateway.service import gateway_embed
from app.vector import vector_db

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Cross-session semantic + keyword search across processed documents."""

    async def search(self, query: str, doc_type: str | None = None, limit: int = 20) -> list[dict]:
        """Search documents by semantic similarity.

        Args:
            query: Natural language query.
            doc_type: Optional document type filter.
            limit: Max results (default 20).

        Returns:
            List of result dicts with session_id, doc_type, fields, similarity.
        """
        try:
            query_embedding = await gateway_embed(query, model="text-embedding-3-large", dimensions=1536)

            filters: dict[str, Any] = {}
            if doc_type:
                filters["doc_type"] = doc_type

            results = await vector_db.search(
                collection="documents",
                vector=query_embedding,
                limit=limit,
                score_threshold=0.5,
                filter_params=filters if filters else None,
            )

            return [
                {
                    "session_id": r.session_id,
                    "doc_type": r.doc_type,
                    "extracted_fields": r.extracted_fields,
                    "similarity": round(r.similarity, 3),
                    "created_at": r.created_at,
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def search_similar_template(self, doc_type: str, layout_fingerprint: str) -> dict | None:
        """Search for a similar document template by layout."""
        if not layout_fingerprint:
            return None
        try:
            embedding = await gateway_embed(layout_fingerprint, model="text-embedding-3-small", dimensions=512)
            results = await vector_db.search(
                collection="templates",
                vector=embedding,
                limit=1,
                score_threshold=0.85,
                filter_params={"doc_type": doc_type} if doc_type else None,
            )
            if results:
                return {
                    "template_id": results[0].session_id,
                    "similarity": results[0].similarity,
                }
            return None
        except Exception as e:
            logger.warning(f"Template search failed (non-critical): {e}")
            return None

    async def find_historical_mapping(self, extracted_key: str, domain: str) -> dict | None:
        """Search past field mappings to reuse human-verified mappings."""
        try:
            embedding = await gateway_embed(extracted_key, model="text-embedding-3-small", dimensions=512)
            results = await vector_db.search(
                collection="field_mappings",
                vector=embedding,
                limit=1,
                score_threshold=0.90,
                filter_params={"domain": domain} if domain else None,
            )
            if results:
                return {
                    "form_field_id": results[0].session_id,
                    "confidence_boost": 0.10,
                }
            return None
        except Exception as e:
            logger.warning(f"Historical mapping search failed: {e}")
            return None


hybrid_retriever = HybridRetriever()
