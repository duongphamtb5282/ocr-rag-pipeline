"""LangGraph state definition for the OCR Form Fill pipeline.

Canonical location — replaces app/graph/state.py
"""

from __future__ import annotations

from typing import Any, Optional

from typing_extensions import TypedDict


class OCRFormFillState(TypedDict):
    """Shared state flowing through all LangGraph agents."""

    # ── Input ──
    session_id: str
    document_path: str
    target_url: Optional[str]

    # ── Stage 1: Document Analysis ──
    doc_type: Optional[str]
    doc_quality: Optional[str]
    ocr_strategy: Optional[str]
    template_id: Optional[str]
    is_new_template: bool

    # ── Stage 2: OCR Output ──
    raw_text: Optional[str]
    layout_blocks: Optional[list]
    markdown_output: Optional[str]
    ocr_fallback_used: bool
    ocr_fallback_reason: Optional[str]

    # ── Stage 3: Extraction ──
    extracted_fields: Optional[dict[str, Any]]
    low_confidence_fields: list[str]

    # ── Stage 4: Form Analysis ──
    form_fields: Optional[list[dict[str, Any]]]
    form_cache_used: bool
    url_safety_ok: bool

    # ── Stage 5: Mapping ──
    field_mappings: Optional[dict[str, Any]]
    unmapped_fields: list[str]

    # ── Stage 6: Human Review ──
    review_status: Optional[str]  # "pending" | "approved" | "rejected" | "corrected"
    human_corrections: Optional[dict[str, Any]]
    human_mappings: Optional[dict[str, Any]]

    # ── Stage 7: Filling ──
    fill_status: Optional[str]  # "success" | "partial" | "failed" | "captcha_blocked"
    fill_errors: Optional[list[dict]]
    submission_proof: Optional[str]
    filled_fields_count: int
    total_fields_count: int
    fill_mode: str  # "test_fill" | "safe_submit" | "full_auto"

    # ── Safeguards ──
    input_guardrails_passed: bool
    pii_detected: bool
    output_guardrails_passed: bool
    prefill_check_passed: bool
    injection_detected: bool
    abuse_flag: Optional[str]

    # ── Metadata ──
    error: Optional[str]
    created_at: str
    completed_at: Optional[str]
    tenant_id: str
    user_id: str
    environment: str


def create_initial_state(
    session_id: str,
    document_path: str,
    target_url: str | None = None,
    tenant_id: str = "default",
    user_id: str = "anonymous",
    environment: str = "development",
) -> dict:
    """Create a fresh state for a new session."""
    from datetime import datetime, timezone
    return {
        "session_id": session_id,
        "document_path": document_path,
        "target_url": target_url,
        "doc_type": None,
        "doc_quality": None,
        "ocr_strategy": None,
        "template_id": None,
        "is_new_template": False,
        "raw_text": None,
        "layout_blocks": None,
        "markdown_output": None,
        "ocr_fallback_used": False,
        "ocr_fallback_reason": None,
        "extracted_fields": None,
        "low_confidence_fields": [],
        "form_fields": None,
        "form_cache_used": False,
        "url_safety_ok": True,
        "field_mappings": None,
        "unmapped_fields": [],
        "review_status": "pending",
        "human_corrections": None,
        "human_mappings": None,
        "fill_status": None,
        "fill_errors": None,
        "submission_proof": None,
        "filled_fields_count": 0,
        "total_fields_count": 0,
        "fill_mode": "safe_submit",
        "input_guardrails_passed": False,
        "pii_detected": False,
        "output_guardrails_passed": False,
        "prefill_check_passed": False,
        "injection_detected": False,
        "abuse_flag": None,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "environment": environment,
    }
