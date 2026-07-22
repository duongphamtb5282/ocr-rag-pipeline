"""Abuse detection — rate limits and suspicious pattern detection."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

SUSPICIOUS_DOMAINS: list[str] = []


class AbuseDetector:
    """Detects and prevents abusive usage patterns."""

    RATE_LIMITS = {
        "anonymous":       {"uploads_per_hour": 5,   "sessions_per_day": 10},
        "authenticated":   {"uploads_per_hour": 50,  "sessions_per_day": 200},
        "enterprise":      {"uploads_per_hour": 500, "sessions_per_day": 2000},
    }

    def __init__(self):
        self._uploads: dict[str, list[float]] = defaultdict(list)

    async def check_upload_allowed(self, user_id: str, tenant_id: str, target_url: str | None = None) -> dict:
        """Check if an upload is allowed based on rate limits and abuse patterns."""
        now = time.time()

        # 1. Clean old entries
        self._uploads[user_id] = [t for t in self._uploads[user_id] if now - t < 3600]

        # 2. Check upload rate
        recent_count = len(self._uploads[user_id])
        tier = "authenticated"
        limit = self.RATE_LIMITS.get(tier, self.RATE_LIMITS["authenticated"])
        if recent_count >= limit["uploads_per_hour"]:
            return {"allowed": False, "reason": "rate_limit_exceeded", "retry_after_s": 3600 - (now - self._uploads[user_id][0])}

        # 3. Suspicious domain check
        if target_url:
            import re
            for domain in SUSPICIOUS_DOMAINS:
                if re.search(domain, target_url, re.IGNORECASE):
                    logger.warning(f"Suspicious domain blocked: {target_url}")
                    return {"allowed": False, "reason": "suspicious_domain"}

        # 4. Record upload
        self._uploads[user_id].append(now)
        return {"allowed": True}


abuse_detector = AbuseDetector()
