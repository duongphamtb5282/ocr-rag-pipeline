"""Immutable audit logger — INSERT-only event recording for compliance."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime

from app.db.database import get_session_factory
from app.models.audit_log import AuditLogModel

logger = logging.getLogger(__name__)


class AuditLogger:
    """Append-only audit trail for all system events."""

    async def log(self, event: str, session_id: str, details: dict | None = None, tenant_id: str = "default", user_id: str = "anonymous"):
        """Record an event to the immutable audit log."""
        try:
            details_json = json.dumps(details or {}, default=str)
            record_hash = self._compute_hash(event, session_id, details_json)

            factory = await get_session_factory()
            async with factory() as db_session:
                log_entry = AuditLogModel(
                    event=event,
                    session_id=session_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    details=details_json,
                    hash=record_hash,
                )
                db_session.add(log_entry)
                await db_session.commit()

            logger.info(f"Audit: {event} | session={session_id[:8]}")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    async def log_session_complete(self, state: dict):
        """Log session completion with all key metrics."""
        await self.log(
            event="session_completed",
            session_id=state.get("session_id", ""),
            tenant_id=state.get("tenant_id", "default"),
            user_id=state.get("user_id", "anonymous"),
            details={
                "doc_type": state.get("doc_type"),
                "status": state.get("fill_status"),
                "field_count": len(state.get("extracted_fields", {}) or {}),
                "mapping_count": len(state.get("field_mappings", {}) or {}),
                "correction_count": len(state.get("human_corrections", {}) or {}),
                "pii_detected": state.get("pii_detected"),
                "injection_detected": state.get("injection_detected"),
                "ocr_fallback_used": state.get("ocr_fallback_used"),
                "fill_mode": state.get("fill_mode"),
            },
        )

    async def log_guardrail_block(self, state: dict, guardrail: str, reason: str):
        """Log a guardrail block event."""
        await self.log(
            event=f"guardrail_blocked_{guardrail}",
            session_id=state.get("session_id", ""),
            tenant_id=state.get("tenant_id", "default"),
            user_id=state.get("user_id", "anonymous"),
            details={"guardrail": guardrail, "reason": reason},
        )

    def _compute_hash(self, event: str, session_id: str, details: str) -> str:
        """Compute SHA-256 hash for integrity verification."""
        content = f"{event}|{session_id}|{datetime.utcnow().isoformat()}|{details}"
        return hashlib.sha256(content.encode()).hexdigest()


audit_logger = AuditLogger()
