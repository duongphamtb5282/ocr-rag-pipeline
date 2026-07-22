"""AutoSwitcher — automatic provider switching based on system conditions."""

from __future__ import annotations

import logging
import time
from datetime import datetime

from app.gateway.budget import budget_controller
from app.gateway.registry import registry
from app.gateway.router import ROUTE_STRATEGIES, router

logger = logging.getLogger(__name__)


class AutoSwitcher:
    """Monitors conditions and auto-switches provider strategies."""

    def __init__(self):
        self._cooldowns: dict[str, float] = {}
        self._provider_disabled_at: dict[str, float] = {}
        self._action_log: list[dict] = []

    async def evaluate(self):
        """Evaluate all rules and execute any triggered actions."""
        now = time.time()
        daily_pct = budget_controller.daily_usage_pct()
        actions = []

        # Rule 1: Budget 80% -> downgrade non-critical routes
        if daily_pct >= 80 and self._can_fire("budget_80", 30):
            logger.info(f"AutoSwitcher: Budget at {daily_pct:.0f}% -> downgrading non-critical routes")
            for route in ["doc_classification", "semantic_mapping", "form_analysis", "embedding"]:
                if ROUTE_STRATEGIES.get(route) != "cost_optimized":
                    router.set_route_strategy(route, "cost_optimized")
                    actions.append({"rule": "budget_80", "action": f"downgraded {route} to cost_optimized"})

        # Rule 2: Budget 95% -> downgrade everything
        if daily_pct >= 95 and self._can_fire("budget_95", 15):
            logger.warning(f"AutoSwitcher: Budget critical ({daily_pct:.0f}%) -> downgrading ALL routes")
            router.set_global_strategy("cost_optimized")
            actions.append({"rule": "budget_95", "action": "downgraded all routes to cost_optimized"})

        # Rule 3: Weekend economy
        day_name = datetime.now().strftime("%A")
        if day_name in ("Saturday", "Sunday") and self._can_fire("weekend", 60):
            logger.info(f"AutoSwitcher: Weekend mode -> cost_optimized")
            router.set_global_strategy("cost_optimized")
            actions.append({"rule": "weekend", "action": "set global strategy to cost_optimized"})

        self._action_log.extend(actions)

    def _can_fire(self, rule_name: str, cooldown_minutes: int) -> bool:
        now = time.time()
        last = self._cooldowns.get(rule_name, 0)
        if now - last > cooldown_minutes * 60:
            self._cooldowns[rule_name] = now
            return True
        return False

    def get_recent_actions(self, limit: int = 10) -> list[dict]:
        return self._action_log[-limit:]


auto_switcher = AutoSwitcher()
