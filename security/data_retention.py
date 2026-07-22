"""Data retention policy — auto-deletion and GDPR compliance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.db.database import get_session_factory

logger = logging.getLogger(__name__)


class DataRetention:
    """Manages document lifecycle, retention, and GDPR deletion."""

    RETENTION = {
        "completed": settings.RETENTION_COMPLETED_DAYS,
        "failed": settings.RETENTION_FAILED_DAYS,
        "abandoned": settings.RETENTION_ABANDONED_DAYS,
    }

    async def cleanup_expired(self):
        """Delete all documents that have exceeded their retention period."""
        now = datetime.now(timezone.utc)
        factory = await get_session_factory()

        async with factory() as db:
            for status, days in self.RETENTION.items():
                cutoff = now - timedelta(days=days)
                query = (
                    f"UPDATE sessions SET deleted_at = :now, "
                    f"raw_text = NULL, extracted_fields = NULL, "
                    f"field_mappings = NULL, human_corrections = NULL, "
                    f"document_path = NULL "
                    f"WHERE status = :status AND completed_at < :cutoff AND deleted_at IS NULL"
                )
                await db.execute(query, {"now": now, "status": status, "cutoff": cutoff})
            await db.commit()

        logger.info("Data retention cleanup completed")

    async def delete_session_data(self, session_id: str, reason: str = "user_request"):
        """GDPR right-to-deletion: permanently remove session data."""
        factory = await get_session_factory()
        async with factory() as db:
            await db.execute(
                "UPDATE sessions SET "
                "raw_text = NULL, extracted_fields = NULL, "
                "field_mappings = NULL, human_corrections = NULL, "
                "document_path = NULL, deleted_at = :now, "
                "deletion_reason = :reason "
                "WHERE session_id = :sid",
                {"sid": session_id, "now": datetime.now(timezone.utc), "reason": reason},
            )
            await db.commit()

        logger.info(f"Session {session_id} deleted: {reason}")

    async def cleanup_uploaded_file(self, file_path: str):
        """Delete an uploaded file from disk."""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")


data_retention = DataRetention()
