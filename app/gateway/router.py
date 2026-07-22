"""Cost-aware router — resolves provider+model per LLM request."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.config import settings
from app.gateway.budget import BudgetDecision, budget_controller
from app.gateway.registry import registry

logger = logging.getLogger(__name__)

SWITCHING_STRATEGIES = {
    "cost_optimized":    "cheapest",
    "quality_optimized": "best",
    "balanced":          "best",
    "manual":            "manual",
}

ROUTE_STRATEGIES: dict[str, str] = {
    "vision_ocr":         "quality_optimized",
    "field_extraction":   "quality_optimized",
    "doc_classification": "cost_optimized",
    "semantic_mapping":   "cost_optimized",
    "form_analysis":      "cost_optimized",
    "embedding":          "cost_optimized",
    "rerank":             "cost_optimized",
}


@dataclass
class RouteDecision:
    provider: str
    model: str
    estimated_cost: float = 0.0
    budget_tier_used: str = "any"
    cached: bool = False


@dataclass
class LLMRequest:
    session_id: str
    agent: str
    route_key: str
    system_prompt: str = ""
    messages: list = field(default_factory=list)
    images: list | None = None
    max_tokens: int = 1024
    temperature: float = 0.0
    estimated_tokens: int = 500
    priority: str = "normal"


@dataclass
class GatewayResponse:
    content: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cached: bool = False


class CostAwareRouter:
    """Routes LLM calls based on capability, budget, strategy, and provider health."""

    def __init__(self):
        self._manual_overrides: dict[str, RouteDecision] = {}
        self._global_strategy: str = settings.LLM_GATEWAY_STRATEGY

    def set_global_strategy(self, strategy: str):
        self._global_strategy = strategy
        logger.info(f"Global strategy set to: {strategy}")

    def set_route_strategy(self, route: str, strategy: str):
        ROUTE_STRATEGIES[route] = strategy
        logger.info(f"Route {route} strategy set to: {strategy}")

    def set_manual_override(self, route: str, provider: str, model: str):
        self._manual_overrides[route] = RouteDecision(provider=provider, model=model, budget_tier_used="manual_override")
        logger.info(f"Manual override for {route}: {provider}/{model}")

    def clear_manual_override(self, route: str):
        self._manual_overrides.pop(route, None)
        logger.info(f"Manual override cleared for {route}")

    def get_active_overrides(self) -> dict:
        return {k: {"provider": v.provider, "model": v.model} for k, v in self._manual_overrides.items()}

    def get_active_strategies(self) -> dict:
        return dict(ROUTE_STRATEGIES)

    async def resolve_route(self, request: LLMRequest) -> RouteDecision:
        """Resolve the best provider+model for a given request."""

        # 1. Check manual override
        if request.route_key in self._manual_overrides:
            return self._manual_overrides[request.route_key]

        # 2. Check budget
        estimated_cost = request.estimated_tokens * 0.01 / 1000
        budget_check = budget_controller.check_call_budget(
            request.route_key, estimated_cost, request.session_id, request.priority
        )
        if not budget_check.allowed:
            logger.warning(f"Budget blocked call: {request.route_key} — {budget_check.reason}")

        # 3. Determine budget tier
        strategy = ROUTE_STRATEGIES.get(request.route_key, self._global_strategy)
        default_tier = SWITCHING_STRATEGIES.get(strategy, "best")
        budget_tier = budget_check.force_tier or budget_check.suggest_tier or default_tier

        # 4. Get available models
        capability = self._route_to_capability(request.route_key)
        candidates = registry.get_available_models(capability=capability, budget_tier=budget_tier)
        if not candidates:
            # Fallback: try any capability
            candidates = registry.get_available_models(capability=capability, budget_tier="any")
        if not candidates:
            raise RuntimeError(f"No available provider for {request.route_key}")

        chosen = candidates[0]
        return RouteDecision(
            provider=chosen.provider,
            model=chosen.model_id,
            estimated_cost=estimated_cost,
            budget_tier_used=budget_tier,
        )

    def _route_to_capability(self, route_key: str) -> str:
        mapping = {
            "vision_ocr": "vision",
            "field_extraction": "extraction",
            "doc_classification": "classification",
            "semantic_mapping": "mapping",
            "form_analysis": "classification",
            "embedding": "embedding",
            "rerank": "classification",
        }
        return mapping.get(route_key, "classification")


router = CostAwareRouter()
