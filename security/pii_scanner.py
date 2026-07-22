"""PII scanner — detects sensitive data in extracted fields."""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

PII_PATTERNS = {
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b\+?1?\d{10,15}\b",
    "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
}


class PIIScanner:
    """Scans extracted field values for personally identifiable information."""

    async def scan_fields(self, extracted_fields: dict) -> dict:
        """Scan all extracted field values for PII."""
        findings = []
        for field_key, field_data in extracted_fields.items():
            value = str(field_data.get("value", ""))
            for pii_type, pattern in PII_PATTERNS.items():
                matches = re.finditer(pattern, value)
                for m in matches:
                    findings.append({
                        "field": field_key,
                        "type": pii_type,
                        "masked": self._mask(m.group(), pii_type),
                        "position": m.start(),
                    })

        return {
            "has_pii": len(findings) > 0,
            "findings": findings,
        }

    def _mask(self, value: str, pii_type: str) -> str:
        """Mask sensitive data for display."""
        if pii_type in ("ssn", "credit_card"):
            return "***" + value[-4:]
        if pii_type == "email":
            parts = value.split("@")
            return f"{parts[0][:2]}***@{parts[1]}"
        return "***" + value[-4:]


pii_scanner = PIIScanner()
