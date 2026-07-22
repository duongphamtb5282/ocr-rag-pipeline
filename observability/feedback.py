"""Feedback capture — records user corrections and satisfaction signals.

Tracks:
- Per-field correction rate (how often users change extracted values)
- Per-session satisfaction (thumbs up/down from review UI)
- Per-route accuracy (which routes produce the most corrections)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FEEDBACK_DIR = Path(__file__).parent.parent / "data" / "feedback"


class FeedbackTracker:
    """Tracks user feedback and corrections for quality improvement."""

    def __init__(self) -> None:
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        self._corrections: list[dict[str, Any]] = []
        self._ratings: list[dict[str, Any]] = []

    def record_correction(
        self,
        session_id: str,
        field_name: str,
        original_value: str,
        corrected_value: str,
        route: str = "",
    ) -> None:
        """Record a user correction to an extracted field."""
        record = {
            "session_id": session_id,
            "field_name": field_name,
            "original_value": original_value,
            "corrected_value": corrected_value,
            "route": route,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._corrections.append(record)
        self._persist()
        logger.debug("Feedback: correction recorded for %s/%s", session_id, field_name)

    def record_rating(
        self, session_id: str, rating: int, comment: str = ""
    ) -> None:
        """Record a user satisfaction rating (1-5)."""
        record = {
            "session_id": session_id,
            "rating": max(1, min(5, rating)),
            "comment": comment,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._ratings.append(record)
        self._persist()

    def correction_rate(self) -> float:
        """Fraction of sessions that had at least one correction."""
        if not self._corrections:
            return 0.0
        sessions_with_corrections = len(set(r["session_id"] for r in self._corrections))
        sessions_with_ratings = len(set(r["session_id"] for r in self._ratings))
        total = max(sessions_with_ratings, 1)
        return round(sessions_with_corrections / total, 3)

    def avg_rating(self) -> float:
        """Average user satisfaction rating."""
        if not self._ratings:
            return 0.0
        return round(sum(r["rating"] for r in self._ratings) / len(self._ratings), 2)

    def most_corrected_fields(self, top_n: int = 10) -> list[dict[str, Any]]:
        """Fields most frequently corrected by users."""
        counts: dict[str, int] = defaultdict(int)
        for r in self._corrections:
            counts[r["field_name"]] += 1
        sorted_fields = sorted(counts.items(), key=lambda x: -x[1])
        return [
            {"field_name": name, "correction_count": count}
            for name, count in sorted_fields[:top_n]
        ]

    def summary(self) -> dict[str, Any]:
        return {
            "total_corrections": len(self._corrections),
            "total_ratings": len(self._ratings),
            "correction_rate": self.correction_rate(),
            "avg_rating": self.avg_rating(),
            "most_corrected_fields": self.most_corrected_fields(),
        }

    def _persist(self) -> None:
        """Persist feedback data to disk."""
        data = {
            "corrections": self._corrections[-500:],  # Keep last 500
            "ratings": self._ratings[-500:],
        }
        path = FEEDBACK_DIR / "feedback_log.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


feedback_tracker = FeedbackTracker()
