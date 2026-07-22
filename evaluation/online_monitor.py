"""Online quality monitoring — tracks production quality metrics in real-time.

Monitors:
- Extraction accuracy (user corrections / total fields)
- Model performance per route (latency, error rate)
- Cost trends per session and per route
- User feedback scores
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MONITOR_DIR = Path(__file__).parent / "eval_results"


class OnlineMonitor:
    """Tracks production quality metrics over sliding windows."""

    def __init__(self, window_hours: int = 24):
        self.window_hours = window_hours
        self._sessions: dict[str, dict[str, Any]] = {}
        self._errors: list[dict[str, Any]] = []
        MONITOR_DIR.mkdir(parents=True, exist_ok=True)

    def record_session(self, session_id: str, data: dict[str, Any]) -> None:
        """Record a completed session's quality data."""
        self._sessions[session_id] = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        }
        self._persist()

    def record_error(self, session_id: str, route: str, error: str) -> None:
        """Record a production error for monitoring."""
        record = {
            "session_id": session_id,
            "route": route,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._errors.append(record)
        logger.warning("Quality monitor error: %s @ %s — %s", session_id, route, error)
        self._persist()

    @property
    def _cutoff(self) -> datetime:
        return datetime.utcnow() - timedelta(hours=self.window_hours)

    def accuracy_rate(self) -> float:
        """Fraction of fields that required no human correction."""
        total_fields = 0
        corrected_fields = 0
        cutoff = self._cutoff

        for s in self._sessions.values():
            ts = datetime.fromisoformat(s.get("timestamp", "2000-01-01"))
            if ts < cutoff:
                continue
            total_fields += s.get("total_fields", 0)
            corrected_fields += s.get("corrected_fields", 0)

        if total_fields == 0:
            return 1.0
        return round(1.0 - (corrected_fields / total_fields), 3)

    def error_rate(self) -> float:
        """Fraction of sessions with errors within the window."""
        cutoff = self._cutoff
        recent_sessions = sum(
            1 for s in self._sessions.values()
            if datetime.fromisoformat(s.get("timestamp", "2000-01-01")) >= cutoff
        )
        recent_errors = sum(
            1 for e in self._errors
            if datetime.fromisoformat(e["timestamp"]) >= cutoff
        )
        if recent_sessions == 0:
            return 0.0
        return round(recent_errors / recent_sessions, 3)

    def route_performance(self) -> dict[str, dict[str, float]]:
        """Per-route performance: avg latency, error count."""
        route_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"calls": 0, "errors": 0, "total_latency": 0.0}
        )
        cutoff = self._cutoff

        for s in self._sessions.values():
            ts = datetime.fromisoformat(s.get("timestamp", "2000-01-01"))
            if ts < cutoff:
                continue
            for route, metrics in s.get("route_metrics", {}).items():
                route_stats[route]["calls"] += metrics.get("calls", 1)
                route_stats[route]["errors"] += metrics.get("errors", 0)
                route_stats[route]["total_latency"] += metrics.get("latency_ms", 0)

        result = {}
        for route, stats in route_stats.items():
            result[route] = {
                "calls": stats["calls"],
                "errors": stats["errors"],
                "avg_latency_ms": round(stats["total_latency"] / stats["calls"], 1) if stats["calls"] else 0,
                "error_rate": round(stats["errors"] / stats["calls"], 3) if stats["calls"] else 0,
            }
        return result

    def summary(self) -> dict[str, Any]:
        """Full monitoring summary."""
        return {
            "window_hours": self.window_hours,
            "sessions_tracked": len(self._sessions),
            "accuracy_rate": self.accuracy_rate(),
            "error_rate": self.error_rate(),
            "route_performance": self.route_performance(),
        }

    def _persist(self) -> None:
        """Persist current state to disk."""
        path = MONITOR_DIR / "online_monitor_state.json"
        data = {
            "sessions": self._sessions,
            "errors": self._errors[-100:],  # Keep last 100 errors
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


online_monitor = OnlineMonitor()
