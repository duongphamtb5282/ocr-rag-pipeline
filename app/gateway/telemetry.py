"""LLM call telemetry — token, cost, and latency tracking."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

from app.gateway.budget import budget_controller

logger = logging.getLogger(__name__)

COST_PER_1K_TOKENS: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4o":              {"input": 0.005,  "output": 0.015},
        "gpt-4o-mini":         {"input": 0.00015, "output": 0.0006},
        "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
        "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    },
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 0.003,  "output": 0.015},
        "claude-haiku-4-20251001":  {"input": 0.00025, "output": 0.00125},
    },
    # Azure OpenAI prices (2026, [ASSUMPTION] — directional; Azure bills by
    # deployment, consult your resource's pricing page to update).
    "azure": {
        "gpt-4o":              {"input": 0.0025, "output": 0.01},
        "gpt-4o-mini":         {"input": 0.00015, "output": 0.0006},
        "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
        "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    },
}


@dataclass
class CallRecord:
    timestamp: str
    session_id: str
    agent: str
    route_key: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    success: bool
    cached: bool
    error: str | None = None


class CostTracker:
    """Tracks LLM costs at call, session, and aggregate levels."""

    def __init__(self):
        self.call_log: list[CallRecord] = []
        self.cache_savings: float = 0.0

    def record_call(
        self,
        session_id: str,
        agent: str,
        route_key: str,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        success: bool,
        cached: bool = False,
        error: str | None = None,
    ):
        cost = 0.0
        if not cached:
            cost = self._calculate_cost(provider, model, tokens_in, tokens_out)
            budget_controller.record_spend(session_id, cost)
        else:
            saved = self._calculate_cost(provider, model, tokens_in, tokens_out)
            self.cache_savings += saved

        record = CallRecord(
            timestamp=datetime.utcnow().isoformat(),
            session_id=session_id,
            agent=agent,
            route_key=route_key,
            provider=provider,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            latency_ms=latency_ms,
            success=success,
            cached=cached,
            error=error,
        )
        self.call_log.append(record)
        logger.debug(f"LLM call: {route_key}@{provider}/{model} ${cost:.6f} {latency_ms:.0f}ms")

    def _calculate_cost(self, provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
        prices = COST_PER_1K_TOKENS.get(provider, {}).get(model, {"input": 0.0, "output": 0.0})
        return (tokens_in / 1000 * prices["input"]) + (tokens_out / 1000 * prices["output"])

    def session_cost(self, session_id: str) -> float:
        return sum(r.cost_usd for r in self.call_log if r.session_id == session_id)

    def total_calls(self) -> int:
        return len(self.call_log)

    def avg_cost_per_call(self) -> float:
        if not self.call_log:
            return 0.0
        return sum(r.cost_usd for r in self.call_log) / len(self.call_log)

    def p95_latency(self) -> float:
        if not self.call_log:
            return 0.0
        latencies = sorted(r.latency_ms for r in self.call_log)
        idx = int(len(latencies) * 0.95)
        return latencies[idx]

    def daily_summary(self) -> dict:
        return {
            "total_cost": round(budget_controller.daily_remaining(), 4),
            "cache_savings": round(self.cache_savings, 4),
            "total_calls": self.total_calls(),
            "avg_cost_per_call": round(self.avg_cost_per_call(), 6),
            "p95_latency_ms": round(self.p95_latency(), 1),
        }


cost_tracker = CostTracker()
