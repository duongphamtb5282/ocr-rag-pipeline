"""Conditional routing functions for the LangGraph.

Canonical location — replaces app/graph/routers.py
"""

from __future__ import annotations

from graph.state import OCRFormFillState


def has_target_url(state: OCRFormFillState) -> bool:
    """Check if the session has a target URL."""
    return bool(state.get("target_url"))


def is_approved(state: OCRFormFillState) -> bool:
    """Check if human approved the review."""
    return state.get("review_status") in ("approved", "corrected")


def fill_successful(state: OCRFormFillState) -> bool:
    """Check if form filling was successful."""
    return state.get("fill_status") == "success"


def all_guardrails_passed(state: OCRFormFillState) -> bool:
    """Check if all safeguard checks passed."""
    return (
        state.get("input_guardrails_passed", False)
        and state.get("output_guardrails_passed", False)
        and state.get("prefill_check_passed", False)
    )
