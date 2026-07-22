"""Cost observability — wraps gateway cost tracking for per-session and aggregate views.

This module re-exports the gateway cost tracker for use by observability
tooling, and adds higher-level aggregation (per-route, per-day, per-session).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from app.gateway.telemetry import cost_tracker as _gateway_tracker

logger = logging.getLogger(__name__)


def session_cost(session_id: str) -> float:
    """Total LLM cost for a session in USD."""
    return round(_gateway_tracker.session_cost(session_id), 6)


def daily_cost() -> float:
    """Estimated cost for today across all sessions."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total = 0.0
    for record in _gateway_tracker.call_log:
        try:
            ts = datetime.fromisoformat(record.timestamp)
            if ts >= today_start:
                total += record.cost_usd
        except (ValueError, TypeError):
            pass
    return round(total, 4)


def cost_by_route() -> dict[str, float]:
    """Cost breakdown per route key."""
    breakdown: dict[str, float] = {}
    for record in _gateway_tracker.call_log:
        route = record.route_key or "unknown"
        breakdown[route] = round(breakdown.get(route, 0.0) + record.cost_usd, 6)
    return breakdown


def cost_by_agent() -> dict[str, float]:
    """Cost breakdown per agent."""
    breakdown: dict[str, float] = {}
    for record in _gateway_tracker.call_log:
        agent = record.agent or "unknown"
        breakdown[agent] = round(breakdown.get(agent, 0.0) + record.cost_usd, 6)
    return breakdown


def cache_savings() -> float:
    """Total savings from cached LLM responses."""
    return round(_gateway_tracker.cache_savings, 4)


def summary() -> dict[str, Any]:
    """Full cost observability summary."""
    return {
        "daily_cost": daily_cost(),
        "session_cost_average": _gateway_tracker.avg_cost_per_call(),
        "total_calls": _gateway_tracker.total_calls(),
        "p95_latency_ms": _gateway_tracker.p95_latency(),
        "cache_savings": cache_savings(),
        "cost_by_route": cost_by_route(),
        "cost_by_agent": cost_by_agent(),
    }
