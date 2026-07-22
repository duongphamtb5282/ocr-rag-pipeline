"""In-memory vector database backend for development/testing."""

from __future__ import annotations

import logging

import numpy as np

from app.vector import BaseVectorBackend, SearchResult

logger = logging.getLogger(__name__)


class MemoryBackend(BaseVectorBackend):
    """Simple in-memory vector store with cosine similarity search."""

    def __init__(self):
        self._stores: dict[str, dict[str, dict]] = {}

    async def upsert(self, collection: str, point_id: str, vector: list[float], payload: dict):
        if collection not in self._stores:
            self._stores[collection] = {}
        self._stores[collection][point_id] = {"vector": vector, "payload": payload}

    async def search(self, collection: str, query_vector: list[float], limit: int = 10,
                     score_threshold: float = 0.0, filter_params: dict | None = None) -> list[SearchResult]:
        if collection not in self._stores:
            return []

        query_np = np.array(query_vector)
        results = []

        for point_id, point in self._stores[collection].items():
            if filter_params:
                matches = all(point["payload"].get(k) == v for k, v in filter_params.items())
                if not matches:
                    continue
            vec = np.array(point["vector"])
            norm = np.linalg.norm(query_np) * np.linalg.norm(vec)
            similarity = float(np.dot(query_np, vec) / (norm + 1e-10)) if norm > 0 else 0.0
            if similarity >= score_threshold:
                results.append(SearchResult(
                    session_id=point["payload"].get("session_id", point_id),
                    doc_type=point["payload"].get("doc_type"),
                    extracted_fields=point["payload"].get("extracted_fields", {}),
                    similarity=similarity,
                    created_at=point["payload"].get("created_at"),
                ))

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:limit]

    async def delete(self, collection: str, filter_params: dict | None = None):
        if collection not in self._stores:
            return
        if filter_params:
            to_delete = []
            for pid, point in self._stores[collection].items():
                if all(point["payload"].get(k) == v for k, v in filter_params.items()):
                    to_delete.append(pid)
            for pid in to_delete:
                del self._stores[collection][pid]
        else:
            self._stores[collection] = {}

    async def create_collection(self, collection: str, vector_size: int = 1536):
        if collection not in self._stores:
            self._stores[collection] = {}

    async def collection_info(self, collection: str) -> dict:
        if collection not in self._stores:
            return {"exists": False, "points": 0}
        return {"exists": True, "points": len(self._stores[collection])}
