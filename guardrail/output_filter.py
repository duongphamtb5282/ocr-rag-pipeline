"""Output filter — field validation and injection protection before form fill.

Third layer of defense: validates field values, scans for XSS/SQL/template
injection, and ensures required fields are populated.
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = {
    "xss": [
        r"<script[\s>]",
        r"javascript\s*:",
        r"<[^>]+on\w+\s*=",
        r"<iframe[\s>]",
        r"eval\(.*\)",
    ],
    "sql_injection": [
        r"'\s*OR\s*'1'='1",
        r"'\s*OR\s*1\s*=\s*1",
        r"'\s*;\s*DROP\s+TABLE",
        r"'\s*;\s*DELETE\s+FROM",
    ],
    "template_injection": [
        r"\{\{.*\}\}",
        r"\$\{.*\}",
        r"<%.*%>",
    ],
}

FIELD_VALIDATORS = {
    "email": r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}$",
    "phone": r"^\+?\d{7,15}$",
    "date": r"^\d{4}-\d{2}-\d{2}$",
    "zip_code": r"^\d{5}(-\d{4})?$",
    "number": r"^-?\d+(\.\d+)?$",
}


class OutputFilter:
    """Validates field values and scans for injections before form fill."""

    async def validate_all(self, extracted_fields: dict, mappings: dict, form_fields: list) -> dict:
        """Run all output guardrails on mapped fields."""
        issues = []
        injection_detected = False

        for field_key, mapping in mappings.items():
            field_data = extracted_fields.get(field_key, {})
            value = str(field_data.get("value", ""))
            form_field_id = mapping.get("form_field_id", "")

            form_field = next((f for f in form_fields if f.get("field_id") == form_field_id), {})

            # 1. Injection scan
            field_injection = await self._scan_injection(field_key, value)
            if field_injection:
                issues.extend(field_injection)
                injection_detected = True

            # 2. Type validation
            field_type = form_field.get("type", "text")
            if field_type in FIELD_VALIDATORS:
                pattern = FIELD_VALIDATORS[field_type]
                if not re.match(pattern, value.strip()):
                    issues.append({
                        "field": field_key,
                        "type": "validation_error",
                        "message": f"Field '{field_key}' does not match expected format for type '{field_type}'",
                    })

            # 3. Required field check
            if form_field.get("required") and not value.strip():
                issues.append({
                    "field": field_key,
                    "type": "required_missing",
                    "message": f"Required field '{field_key}' has no value",
                })

        return {
            "all_passed": len(issues) == 0,
            "injection_detected": injection_detected,
            "issues": issues,
            "error": issues[0]["message"] if issues else None,
        }

    async def _scan_injection(self, field_key: str, value: str) -> list[dict]:
        """Scan a single field value for injection attacks."""
        findings = []
        for injection_type, patterns in INJECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    findings.append({
                        "field": field_key,
                        "type": f"injection_{injection_type}",
                        "message": f"Potential {injection_type} injection detected in field '{field_key}'",
                    })
        return findings


output_filter = OutputFilter()
