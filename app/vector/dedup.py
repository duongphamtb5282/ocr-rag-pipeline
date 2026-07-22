"""Duplicate document detection — SHA-256 hash + vector similarity."""

from __future__ import annotations

import hashlib
import logging

from app.gateway.service import gateway_embed
from app.vector import vector_db

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detect if the same document was uploaded before."""

    async def check(self, file_path: str, ocr_preview: str = "") -> dict:
        """Check if a document is a duplicate. Returns match info or None."""
        # 1. Fast path: SHA-256 hash
        try:
            file_hash = hashlib.sha256(open(file_path, "rb").read()).hexdigest()
        except Exception:
            file_hash = ""

        # 2. Vector similarity (if we have OCR preview)
        if ocr_preview:
            try:
                embedding = await gateway_embed(ocr_preview[:1000], model="text-embedding-3-large", dimensions=1536)
                similar = await vector_db.search(
                    collection="documents",
                    vector=embedding,
                    limit=1,
                    score_threshold=0.95,
                )
                if similar:
                    return {
                        "is_duplicate": True,
                        "similarity": similar[0].similarity,
                        "existing_session": similar[0].session_id,
                        "method": "vector_similarity",
                    }
            except Exception:
                pass

        return {"is_duplicate": False, "file_hash": file_hash}


duplicate_detector = DuplicateDetector()
