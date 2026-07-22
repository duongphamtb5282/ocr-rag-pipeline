"""Conversation / session management — lifecycle and state persistence.

Tracks session state across the document processing lifecycle:
upload → analyzing → extracting → reviewing → completed (or failed).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

VALID_STATUSES = [
    "uploaded", "analyzing", "extracting", "awaiting_review",
    "filling", "completed", "failed", "cancelled",
]


class ConversationService:
    """Session lifecycle management."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    async def create_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a new processing session."""
        session = {
            "session_id": session_id,
            "status": "uploaded",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        self._sessions[session_id] = session
        logger.info("Session %s created", session_id[:8])
        return session

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID."""
        return self._sessions.get(session_id)

    async def update_status(self, session_id: str, status: str) -> dict[str, Any] | None:
        """Update session status with validation."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Valid: {VALID_STATUSES}")

        session = self._sessions.get(session_id)
        if session is None:
            return None

        session["status"] = status
        session["updated_at"] = datetime.utcnow().isoformat()
        return session

    async def list_sessions(self, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        """List all sessions, optionally filtered by status."""
        sessions = list(self._sessions.values())
        if status:
            sessions = [s for s in sessions if s["status"] == status]
        return sorted(sessions, key=lambda s: s["created_at"], reverse=True)[:limit]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session (GDPR compliance)."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Session %s deleted", session_id[:8])
            return True
        return False


conversation = ConversationService()
