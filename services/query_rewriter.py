"""Query rewriter — LLM-based search query rewriting for better retrieval.

Transforms raw user search queries into optimized queries for
vector search by expanding abbreviations, correcting typos,
and adding context.
"""

from __future__ import annotations

import json
import logging

from app.gateway.router import LLMRequest
from app.gateway.service import gateway_call

logger = logging.getLogger(__name__)

REWRITE_PROMPT = """You are a search query optimizer. Given a user's search query, rewrite it to improve vector search retrieval.

Rules:
1. Expand abbreviations (e.g. "inv" -> "invoice")
2. Fix common OCR typos
3. Add relevant context
4. Keep the original intent

Output ONLY a JSON object: {{"original": str, "rewritten": str, "expanded_terms": [str]}}"""


class QueryRewriter:
    """Rewrites search queries for improved retrieval."""

    async def rewrite(self, query: str, session_id: str = "query_rewrite") -> str:
        """Rewrite a search query for better semantic matching.

        Args:
            query: Raw user search query.
            session_id: Optional session ID for tracing.

        Returns:
            Optimized query string (falls back to original on error).
        """
        if not query or len(query.strip()) < 3:
            return query

        try:
            result = await gateway_call(LLMRequest(
                session_id=session_id,
                agent="query_rewriter",
                route_key="doc_classification",
                system_prompt=REWRITE_PROMPT,
                messages=[{"role": "user", "content": query}],
                max_tokens=128,
                temperature=0.0,
                estimated_tokens=100,
            ))
            parsed = json.loads(result)
            rewritten = parsed.get("rewritten", query)
            logger.debug("Query rewritten: '%s' -> '%s'", query, rewritten)
            return rewritten
        except Exception as e:
            logger.warning(f"Query rewrite failed, using original: {e}")
            return query


query_rewriter = QueryRewriter()
