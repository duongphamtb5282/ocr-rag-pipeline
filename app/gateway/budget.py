"""Budget controller — enforces hard/soft limits per day, session, and route."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class BudgetDecision:
    allowed: bool
    reason: str = ""
    force_tier: str | None = None
    suggest_tier: str | None = None
    warn: bool = False


class BudgetController:
    """Central budget tracking and enforcement."""

    ROUTE_BUDGETS = {
        "vision_ocr":         {"max_per_call": 0.03},
        "field_extraction":   {"max_per_call": 0.02},
        "doc_classification": {"max_per_call": 0.005},
        "semantic_mapping":   {"max_per_call": 0.005},
        "form_analysis":      {"max_per_call": 0.01},
        "embedding":          {"max_per_call": 0.0001},
    }

    def __init__(self):
        self._daily_spent: float = 0.0
        self._monthly_spent: float = 0.0
        self._session_spent: dict[str, float] = {}
        self._current_date: date = date.today()

    def _reset_if_new_day(self):
        today = date.today()
        if today != self._current_date:
            self._daily_spent = 0.0
            self._current_date = today

    def record_spend(self, session_id: str, cost: float):
        self._reset_if_new_day()
        self._daily_spent += cost
        self._monthly_spent += cost
        self._session_spent[session_id] = self._session_spent.get(session_id, 0.0) + cost

    def session_spent(self, session_id: str) -> float:
        return self._session_spent.get(session_id, 0.0)

    def session_remaining(self, session_id: str) -> float:
        return max(settings.LLM_MAX_PER_SESSION_USD - self.session_spent(session_id), 0.0)

    def daily_remaining(self) -> float:
        self._reset_if_new_day()
        return max(settings.LLM_DAILY_BUDGET_USD - self._daily_spent, 0.0)

    def daily_usage_pct(self) -> float:
        self._reset_if_new_day()
        if settings.LLM_DAILY_BUDGET_USD <= 0:
            return 0.0
        return (self._daily_spent / settings.LLM_DAILY_BUDGET_USD) * 100

    def monthly_remaining(self) -> float:
        return max(settings.LLM_MONTHLY_BUDGET_USD - self._monthly_spent, 0.0)

    def check_call_budget(self, route_key: str, estimated_cost: float, session_id: str, priority: str = "normal") -> BudgetDecision:
        """Check if a call is within budget. Returns decision with routing hints."""
        self._reset_if_new_day()

        # 1. Daily hard limit
        daily_remaining = self.daily_remaining()
        if daily_remaining <= 0:
            return BudgetDecision(allowed=False, reason="daily_hard_limit_reached")

        # 2. Monthly hard limit
        if self._monthly_spent >= settings.LLM_MONTHLY_BUDGET_USD:
            return BudgetDecision(allowed=False, reason="monthly_hard_limit_reached")

        # 3. Per-session budget
        session_remaining = self.session_remaining(session_id)
        if estimated_cost > session_remaining:
            return BudgetDecision(
                allowed=False,
                reason="session_budget_exceeded",
                suggest_tier="cheapest",
            )

        # 4. Per-route budget
        route_budget = self.ROUTE_BUDGETS.get(route_key, {}).get("max_per_call", float("inf"))
        if estimated_cost > route_budget * 1.5:
            return BudgetDecision(allowed=True, warn=True, reason=f"route_budget_exceeded (${estimated_cost:.3f} > ${route_budget:.3f})")

        # 5. Soft limits for auto-downgrade
        daily_pct = self.daily_usage_pct()
        if daily_pct >= 95:
            return BudgetDecision(allowed=True, force_tier="cheapest", reason="daily_critical_limit")
        if daily_pct >= 80:
            return BudgetDecision(allowed=True, suggest_tier="cheapest", reason="daily_soft_limit")

        return BudgetDecision(allowed=True)

    def current_status(self) -> dict:
        self._reset_if_new_day()
        return {
            "daily": {
                "spent": round(self._daily_spent, 2),
                "limit": settings.LLM_DAILY_BUDGET_USD,
                "remaining": round(self.daily_remaining(), 2),
                "usage_pct": round(self.daily_usage_pct(), 1),
            },
            "monthly": {
                "spent": round(self._monthly_spent, 2),
                "limit": settings.LLM_MONTHLY_BUDGET_USD,
                "remaining": round(self.monthly_remaining(), 2),
            },
        }


budget_controller = BudgetController()
