"""Vector database service — document indexing, semantic search, dedup.
Supports in-memory (dev), Qdrant (production), and pgvector backends.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    session_id: str
    doc_type: str | None
    extracted_fields: dict
    similarity: float
    created_at: str | None


class VectorDB:
    """Vector database abstraction — auto-selects backend based on config."""

    def __init__(self):
        backend_type = settings.VECTOR_DB_TYPE
        self._backend: BaseVectorBackend

        if backend_type == "qdrant":
            from app.vector.backends.qdrant_backend import QdrantBackend
            self._backend = QdrantBackend(
                url=settings.VECTOR_DB_URL,
                api_key=settings.VECTOR_DB_API_KEY,
            )
        elif backend_type == "pgvector":
            from app.vector.backends.pgvector_backend import PgVectorBackend
            self._backend = PgVectorBackend(settings.DATABASE_URL)
        else:
            from app.vector.backends.memory_backend import MemoryBackend
            self._backend = MemoryBackend()

        logger.info(f"Vector DB backend: {backend_type} ({type(self._backend).__name__})")

    async def upsert(self, collection: str, point_id: str, vector: list[float], payload: dict):
        await self._backend.upsert(collection, point_id, vector, payload)

    async def search(self, collection: str, vector: list[float], limit: int = 10,
                     score_threshold: float = 0.0, filter_params: dict | None = None) -> list[SearchResult]:
        return await self._backend.search(collection, vector, limit, score_threshold, filter_params)

    async def delete(self, collection: str, filter_params: dict | None = None):
        await self._backend.delete(collection, filter_params)

    async def create_collection(self, collection: str, vector_size: int = 1536):
        await self._backend.create_collection(collection, vector_size)

    async def collection_info(self, collection: str) -> dict:
        return await self._backend.collection_info(collection)


class BaseVectorBackend:
    """Abstract base for vector DB backends."""

    async def upsert(self, collection: str, point_id: str, vector: list[float], payload: dict):
        raise NotImplementedError

    async def search(self, collection: str, vector: list[float], limit: int,
                     score_threshold: float, filter_params: dict | None) -> list[SearchResult]:
        raise NotImplementedError

    async def delete(self, collection: str, filter_params: dict | None = None):
        raise NotImplementedError

    async def create_collection(self, collection: str, vector_size: int = 1536):
        pass

    async def collection_info(self, collection: str) -> dict:
        return {}


vector_db = VectorDB()
