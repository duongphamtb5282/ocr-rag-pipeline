"""Query router — wraps gateway router as a service for cost-aware LLM routing.

Provides a service-level interface for routing decisions,
consumed by the API layer and agents.
"""

from __future__ import annotations

import logging
from typing import Any

from app.gateway.router import LLMRequest, gateway_router
from app.gateway.service import gateway_call

logger = logging.getLogger(__name__)


class QueryRouter:
    """Service-level interface for cost-aware LLM routing."""

    async def route(self, request: LLMRequest) -> dict[str, Any]:
        """Route an LLM request to the optimal provider.

        Returns:
            Dict with provider, model, cost, and response info.
        """
        result = await gateway_router.route(request)
        return result

    async def call_llm(self, request: LLMRequest) -> str:
        """Make an LLM call via the gateway with full routing.

        Args:
            request: LLM request with session context.

        Returns:
            LLM response text.

        Raises:
            RuntimeError: If all providers fail.
        """
        return await gateway_call(request)

    async def health(self) -> dict[str, Any]:
        """Get routing health: available providers, current strategy, budget status."""
        from app.config import settings
        from app.gateway.budget import budget_controller

        return {
            "strategy": settings.LLM_GATEWAY_STRATEGY,
            "daily_budget": settings.LLM_DAILY_BUDGET_USD,
            "daily_remaining": budget_controller.daily_remaining(),
            "providers": await self._list_available_providers(),
        }

    async def _list_available_providers(self) -> list[str]:
        """List configured providers."""
        from app.config import settings
        providers = []
        if settings.OPENAI_API_KEY:
            providers.append("openai")
        if settings.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        if settings.GOOGLE_API_KEY:
            providers.append("google")
        return providers


query_router = QueryRouter()
