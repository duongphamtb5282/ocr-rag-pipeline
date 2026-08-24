"""Pre-fill safety checks before browser automation."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DESTRUCTIVE_KEYWORDS = ["delete", "remove", "destroy", "terminate", "cancel", "revoke"]


class PrefillSafety:
    """Safety checks performed immediately before form filling."""

    async def check(self, target_url: str) -> dict:
        """Run all pre-fill safety checks."""
        issues = []

        if not target_url:
            return {"passed": False, "error": "No target URL provided", "fill_mode": "none"}

        try:
            parsed = urlparse(target_url)
        except Exception as e:
            return {"passed": False, "error": f"Invalid URL: {e}", "fill_mode": "none"}

        # Scheme check
        if parsed.scheme not in ("http", "https"):
            return {"passed": False, "error": f"Unsupported URL scheme: {parsed.scheme}", "fill_mode": "none"}

        # Destructive action detection
        path_lower = parsed.path.lower()
        for keyword in DESTRUCTIVE_KEYWORDS:
            if keyword in path_lower:
                return {
                    "passed": False,
                    "error": f"URL appears destructive (contains '{keyword}'). Blocked for safety.",
                    "fill_mode": "none",
                }

        return {"passed": True, "fill_mode": "safe_submit", "issues": issues}


prefill_safety = PrefillSafety()
