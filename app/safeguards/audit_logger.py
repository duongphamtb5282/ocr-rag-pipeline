"""Backward-compat shim — use security.audit_logger instead."""

from security.audit_logger import audit_logger, AuditLogger  # noqa: F401
