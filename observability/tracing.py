"""Structured tracing — per-stage timing and metadata capture.

Provides a context manager for tracing individual stages of the
document processing pipeline (OCR, extraction, mapping, filling).
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generator

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """A single traced operation span."""

    name: str
    session_id: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def finish(self, error: str | None = None) -> None:
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 1)
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "session_id": self.session_id,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "error": self.error,
            "timestamp": datetime.utcnow().isoformat(),
        }


class Tracer:
    """Collects and manages trace spans for a session."""

    def __init__(self) -> None:
        self._spans: dict[str, list[Span]] = {}

    @contextmanager
    def trace(
        self, session_id: str, name: str, **metadata: Any
    ) -> Generator[Span, None, None]:
        """Context manager to trace a block of code.

        Usage:
            with tracer.trace(session_id, "ocr_extraction", strategy="doctr") as span:
                result = await run_ocr()
                span.metadata["pages"] = result.page_count
        """
        span = Span(name=name, session_id=session_id, metadata=metadata)
        try:
            yield span
        except Exception as e:
            span.finish(error=str(e))
            raise
        else:
            span.finish()
        finally:
            self._spans.setdefault(session_id, []).append(span)
            logger.debug("Trace [%s] %s: %.1fms", session_id, name, span.duration_ms)

    def get_session_traces(self, session_id: str) -> list[dict[str, Any]]:
        """Get all traces for a session as dicts."""
        return [s.to_dict() for s in self._spans.get(session_id, [])]

    def session_duration_ms(self, session_id: str) -> float:
        """Total duration of all traced operations for a session."""
        spans = self._spans.get(session_id, [])
        if not spans:
            return 0.0
        first = min(s.start_time for s in spans)
        last = max(s.end_time for s in spans if s.end_time)
        return round((last - first) * 1000, 1)

    def clear_session(self, session_id: str) -> None:
        """Clear traces for a completed session."""
        self._spans.pop(session_id, None)


tracer = Tracer()
