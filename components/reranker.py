"""Reranker — cross-encoder style LLM reranking for search precision.

Takes initial retrieval results and re-orders them by relevance
using an LLM call. This is the N+1 stage after initial vector search.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.gateway.router import LLMRequest
from app.gateway.service import gateway_call

logger = logging.getLogger(__name__)


class Reranker:
    """LLM-based reranker to improve search precision."""

    async def rerank(self, query: str, results: list[dict], top_n: int = 5) -> list[dict]:
        """Re-rank search results by relevance using the LLM.

        Args:
            query: The original search query.
            results: Initial search results from the retriever.
            top_n: Number of top results to return after reranking.

        Returns:
            Re-ranked results list.
        """
        if not results:
            return []

        prompt = f"Query: {query}\n\nRank these results by relevance:\n"
        for i, r in enumerate(results):
            prompt += f"{i}. Doc type: {r.get('doc_type', 'unknown')}, "
            prompt += f"Fields: {r.get('extracted_fields', {})}\n"
        prompt += "\nReturn the indices in order of relevance, most relevant first. Format: [2, 0, 1]"

        try:
            response = await gateway_call(LLMRequest(
                session_id="rerank",
                agent="reranker",
                route_key="rerank",
                system_prompt="You are a search relevance reranker. Return indices in order of relevance.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.0,
                estimated_tokens=200,
            ))

            # Parse indices from response
            indices: list[int] = json.loads(response.strip())
            reordered = [results[i] for i in indices if i < len(results)]
            return reordered[:top_n]

        except Exception as e:
            logger.warning(f"Reranking failed, using original order: {e}")
            return results[:top_n]


reranker = Reranker()
