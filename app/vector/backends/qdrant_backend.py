"""Qdrant vector database backend for production use."""

from __future__ import annotations

import logging
from typing import Any

from app.vector import BaseVectorBackend, SearchResult

logger = logging.getLogger(__name__)


class QdrantBackend(BaseVectorBackend):
    """Production-grade vector DB using Qdrant.
    Requires: pip install qdrant-client
    """

    def __init__(self, url: str = "", api_key: str = "", prefer_grpc: bool = True):
        self._url = url or "http://localhost:6333"
        self._api_key = api_key
        self._prefer_grpc = prefer_grpc
        self._client = None
        self._collections: set[str] = set()

    async def _get_client(self):
        """Lazy-initialize Qdrant client."""
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import AsyncQdrantClient
            self._client = AsyncQdrantClient(
                url=self._url,
                api_key=self._api_key or None,
                prefer_grpc=self._prefer_grpc,
            )
            # Verify connection
            await self._client.get_collections()
            logger.info(f"Connected to Qdrant at {self._url}")
            return self._client
        except ImportError:
            logger.warning("qdrant-client not installed. Install with: pip install qdrant-client")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise

    async def _ensure_collection(self, collection: str, vector_size: int = 1536):
        """Create collection if it doesn't exist."""
        if collection in self._collections:
            return
        client = await self._get_client()
        try:
            await client.create_collection(
                collection_name=collection,
                vectors_config={"size": vector_size, "distance": "Cosine"},
            )
            logger.info(f"Created Qdrant collection: {collection} (size={vector_size})")
        except Exception as e:
            # Collection may already exist
            if "already exists" not in str(e).lower():
                logger.warning(f"Could not create collection {collection}: {e}")
        self._collections.add(collection)

    async def upsert(self, collection: str, point_id: str, vector: list[float], payload: dict):
        client = await self._get_client()
        await self._ensure_collection(collection, len(vector))
        from qdrant_client.models import PointStruct
        point = PointStruct(
            id=hash(point_id) % (2**63),  # Qdrant uses unsigned 64-bit ints
            vector=vector,
            payload=payload,
        )
        await client.upsert(collection_name=collection, points=[point])

    async def search(self, collection: str, query_vector: list[float], limit: int = 10,
                     score_threshold: float = 0.0, filter_params: dict | None = None) -> list[SearchResult]:
        client = await self._get_client()
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant_filter = None
        if filter_params:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter_params.items()
            ]
            qdrant_filter = Filter(must=conditions)

        try:
            results = await client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=qdrant_filter,
            )
            return [
                SearchResult(
                    session_id=r.payload.get("session_id", str(r.id)),
                    doc_type=r.payload.get("doc_type"),
                    extracted_fields=r.payload.get("extracted_fields", {}),
                    similarity=r.score,
                    created_at=r.payload.get("created_at"),
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            return []

    async def delete(self, collection: str, filter_params: dict | None = None):
        client = await self._get_client()
        try:
            if filter_params:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                conditions = [
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filter_params.items()
                ]
                await client.delete(
                    collection_name=collection,
                    points_selector=Filter(must=conditions),
                )
            else:
                await client.delete_collection(collection_name=collection)
                self._collections.discard(collection)
        except Exception as e:
            logger.error(f"Qdrant delete failed: {e}")

    async def create_collection(self, collection: str, vector_size: int = 1536):
        await self._ensure_collection(collection, vector_size)

    async def collection_info(self, collection: str) -> dict:
        client = await self._get_client()
        try:
            info = await client.get_collection(collection_name=collection)
            return {
                "exists": True,
                "points": info.points_count,
                "vector_size": info.config.params.vectors.size,
            }
        except Exception:
            return {"exists": False, "points": 0}
