"""pgvector backend for PostgreSQL vector storage."""

from __future__ import annotations

import json
import logging

from app.vector import BaseVectorBackend, SearchResult

logger = logging.getLogger(__name__)


class PgVectorBackend(BaseVectorBackend):
    """pgvector backend using PostgreSQL with pgvector extension.
    Requires: pip install pgvector psycopg2-binary
    """

    def __init__(self, database_url: str = ""):
        self._database_url = database_url
        self._pool = None

    async def _get_pool(self):
        if self._pool is not None:
            return self._pool
        try:
            from psycopg_pool import AsyncConnectionPool
            self._pool = AsyncConnectionPool(self._database_url, min_size=1, max_size=5)
            logger.info("Connected to pgvector")
            await self._init_extensions()
            return self._pool
        except ImportError:
            logger.warning("pgvector dependencies not installed. Install with: pip install pgvector psycopg2-binary")
            raise

    async def _init_extensions(self):
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS vector_docs (
                        id SERIAL PRIMARY KEY,
                        collection TEXT NOT NULL,
                        point_id TEXT NOT NULL,
                        embedding vector(1536),
                        payload JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        UNIQUE(collection, point_id)
                    )
                """)
                await cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_vector_docs_collection
                    ON vector_docs (collection)
                """)
            await conn.commit()

    async def upsert(self, collection: str, point_id: str, vector: list[float], payload: dict):
        pool = await self._get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT INTO vector_docs (collection, point_id, embedding, payload)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (collection, point_id)
                       DO UPDATE SET embedding = EXCLUDED.embedding, payload = EXCLUDED.payload""",
                    (collection, point_id, vector, json.dumps(payload)),
                )
            await conn.commit()

    async def search(self, collection: str, query_vector: list[float], limit: int = 10,
                     score_threshold: float = 0.0, filter_params: dict | None = None) -> list[SearchResult]:
        pool = await self._get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                query = """SELECT point_id, payload, 1 - (embedding <=> %s::vector) as similarity
                           FROM vector_docs
                           WHERE collection = %s
                           AND 1 - (embedding <=> %s::vector) >= %s"""
                params = [query_vector, collection, query_vector, score_threshold]

                if filter_params:
                    for k, v in filter_params.items():
                        query += f" AND payload->>'{k}' = %s"
                        params.append(str(v))

                query += " ORDER BY similarity DESC LIMIT %s"
                params.append(limit)

                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [
                    SearchResult(
                        session_id=row[1].get("session_id", row[0]),
                        doc_type=row[1].get("doc_type"),
                        extracted_fields=row[1].get("extracted_fields", {}),
                        similarity=float(row[2]),
                        created_at=row[1].get("created_at"),
                    )
                    for row in rows
                ]

    async def delete(self, collection: str, filter_params: dict | None = None):
        pool = await self._get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                if filter_params:
                    conditions = " AND ".join(f"payload->>'{k}' = %s" for k in filter_params)
                    await cur.execute(
                        f"DELETE FROM vector_docs WHERE collection = %s AND {conditions}",
                        [collection] + list(filter_params.values()),
                    )
                else:
                    await cur.execute("DELETE FROM vector_docs WHERE collection = %s", [collection])
            await conn.commit()
