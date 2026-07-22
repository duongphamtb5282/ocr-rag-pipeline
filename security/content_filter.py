"""Content filter — content-level filtering and classification.

Additional security layer for filtering inappropriate or dangerous
content detected within document text.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

CONTENT_BLOCKLIST = [
    r"(?i)classified\s+document",
    r"(?i)top\s+secret",
    r"(?i)confidential",
]


class ContentFilter:
    """Filters document content for prohibited or dangerous material."""

    async def filter_text(self, text: str) -> dict[str, Any]:
        """Scan extracted text for blocked content patterns."""
        findings = []
        for pattern in CONTENT_BLOCKLIST:
            matches = re.finditer(pattern, text)
            for m in matches:
                findings.append({
                    "pattern": pattern,
                    "position": m.start(),
                    "matched_text": m.group()[:50],
                })

        return {
            "blocked": len(findings) > 0,
            "findings": findings,
        }

    async def classify_content(self, text: str) -> dict[str, Any]:
        """Classify content category (placeholder for ML classifier)."""
        return {
            "categories": [],
            "safe": True,
        }


content_filter = ContentFilter()
