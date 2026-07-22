"""Validation tools — format validators for extracted field values.

Canonical location — replaces app/graph/tools/validation.py
"""

from __future__ import annotations

import re
from datetime import datetime


class ValidationTools:
    """Format validators for extracted field values."""

    @staticmethod
    def validate_date(value: str) -> dict:
        formats = [("%Y-%m-%d", "ISO"), ("%m/%d/%Y", "US"), ("%d/%m/%Y", "EU"), ("%B %d, %Y", "Long US"), ("%d %B %Y", "Long EU")]
        for fmt, name in formats:
            try:
                dt = datetime.strptime(value.strip(), fmt)
                return {"valid": True, "parsed": dt.isoformat(), "format": name}
            except ValueError:
                continue
        return {"valid": False, "parsed": None, "format": None}

    @staticmethod
    def validate_phone(value: str) -> dict:
        cleaned = re.sub(r"[\s\-\(\)\.]", "", value)
        if cleaned.startswith("+"):
            pattern = r"^\+\d{7,15}$"
        elif cleaned.startswith("0"):
            pattern = r"^0\d{9,10}$"
        else:
            pattern = r"^\d{7,15}$"
        valid = bool(re.match(pattern, cleaned))
        return {"valid": valid, "normalized": f"+{cleaned}" if not cleaned.startswith("+") and valid else cleaned}

    @staticmethod
    def validate_email(value: str) -> dict:
        pattern = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}$"
        return {"valid": bool(re.match(pattern, value.strip()))}

    @staticmethod
    def normalize_currency(value: str) -> dict:
        cleaned = re.sub(r"[^\d.,\-]", "", value).replace(",", "")
        try:
            return {"valid": True, "value": float(cleaned)}
        except ValueError:
            return {"valid": False, "value": None}


validation_tools = ValidationTools()
