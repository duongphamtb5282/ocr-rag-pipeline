"""Backward-compat shim — use security.pii_scanner instead."""

from guardrail.pii_scanner import pii_scanner, PIIScanner  # noqa: F401
