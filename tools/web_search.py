"""Web search tool — placeholder for future web search integration.

Intended to provide agents with web search capability for
contextual enrichment during document analysis.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Web search interface for agents (placeholder)."""

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Execute a web search and return results.

        Placeholder — integrate with Tavily, SerpAPI, or similar.
        """
        logger.info(f"Web search requested (not yet implemented): {query}")
        return []


web_search = WebSearchTool()
