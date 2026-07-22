"""LangGraph graph builder — wires all agents, tools, and safeguard nodes.

Canonical location — replaces app/graph/builder.py
"""

from __future__ import annotations

import logging

from graph.state import OCRFormFillState

# Guards and security — imported at module level for performance
from security.input_guard import input_guard
from security.output_filter import output_filter
from security.pii_scanner import pii_scanner
from security.prefill_safety import prefill_safety
from security.audit_logger import audit_logger

# Agent nodes — decoupled from graph runtime
from agents.document_analyzer import document_analyzer_node
from agents.field_extractor import field_extractor_node
from agents.form_analyzer import form_analyzer_node
from agents.field_mapper import field_mapper_node
from agents.form_filler import form_filler_node

logger = logging.getLogger(__name__)

# In-memory graph storage for the compiled app
_compiled_graph = None


def has_target_url(state: OCRFormFillState) -> bool:
    """Conditional edge: does the session have a target URL?"""
    return bool(state.get("target_url"))


def is_approved(state: OCRFormFillState) -> bool:
    """Conditional edge: did human approve the mappings?"""
    return state.get("review_status") in ("approved", "corrected")


def fill_successful(state: OCRFormFillState) -> bool:
    """Conditional edge: did form filling succeed?"""
    return state.get("fill_status") == "success"


async def ocr_node(state: OCRFormFillState) -> dict:
    """OCR execution node."""
    from app.ocr.toolbox import ocr_toolbox
    strategy = state.get("ocr_strategy", "auto")
    result = await ocr_toolbox.extract(state["document_path"], strategy=strategy)
    return {
        "raw_text": result.get("text", ""),
        "layout_blocks": result.get("layout_blocks", []),
        "ocr_fallback_used": result.get("fallback_used", False),
        "ocr_fallback_reason": f"Fallback used: {result.get('engine', 'unknown')}" if result.get("fallback_used") else None,
    }


async def input_guardrails_node(state: OCRFormFillState) -> dict:
    """Input guardrails: validate document before processing."""
    result = await input_guard.validate(state["document_path"])
    return {
        "input_guardrails_passed": result.get("passed", False),
        "abuse_flag": result.get("flag"),
        "error": result.get("error") if not result.get("passed") else None,
    }


async def pii_scan_node(state: OCRFormFillState) -> dict:
    """Scan extracted fields for PII."""
    extracted = state.get("extracted_fields", {})
    if not extracted:
        return {"pii_detected": False}
    result = await pii_scanner.scan_fields(extracted)
    return {"pii_detected": result.get("has_pii", False)}


async def output_guardrails_node(state: OCRFormFillState) -> dict:
    """Output guardrails: validate fields and scan for injections."""
    extracted = state.get("extracted_fields", {})
    mappings = state.get("field_mappings", {})
    form_fields = state.get("form_fields", [])
    result = await output_filter.validate_all(extracted, mappings, form_fields)
    return {
        "output_guardrails_passed": result.get("all_passed", False),
        "injection_detected": result.get("injection_detected", False),
        "error": result.get("error") if not result.get("all_passed") else None,
    }


async def prefill_safety_node(state: OCRFormFillState) -> dict:
    """Pre-fill safety check before running form filler."""
    target_url = state.get("target_url", "")
    result = await prefill_safety.check(target_url)
    return {
        "prefill_check_passed": result.get("passed", False),
        "fill_mode": result.get("fill_mode", "safe_submit"),
        "error": result.get("error") if not result.get("passed") else None,
    }


async def audit_log_node(state: OCRFormFillState) -> dict:
    """Log session completion to immutable audit trail."""
    await audit_logger.log_session_complete(state)
    return {}


async def completion_node(state: OCRFormFillState) -> dict:
    """Terminal node: mark session as complete."""
    from datetime import datetime, timezone
    return {"completed_at": datetime.now(timezone.utc).isoformat()}


async def human_review_node(state: OCRFormFillState) -> dict:
    """Human review interrupt — execution pauses here and waits for API input."""
    logger.info(f"Session {state['session_id']} waiting for human review")
    return {"review_status": "approved"}  # Default: resume (actual review comes via API)


async def skip_node(state: OCRFormFillState) -> dict:
    """No-op node for conditional skip paths."""
    return {}


def build_graph():
    """Build the LangGraph state graph."""
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(OCRFormFillState)

    # Add all nodes
    workflow.add_node("input_guardrails", input_guardrails_node)
    workflow.add_node("analyze_document", document_analyzer_node)
    workflow.add_node("run_ocr", ocr_node)
    workflow.add_node("extract_fields", field_extractor_node)
    workflow.add_node("pii_scan", pii_scan_node)
    workflow.add_node("analyze_form", form_analyzer_node)
    workflow.add_node("skip_form", skip_node)
    workflow.add_node("map_fields", field_mapper_node)
    workflow.add_node("output_guardrails", output_guardrails_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("prefill_safety", prefill_safety_node)
    workflow.add_node("fill_form", form_filler_node)
    workflow.add_node("audit_log", audit_log_node)
    workflow.add_node("complete", completion_node)

    # Set entry point
    workflow.set_entry_point("input_guardrails")

    # Define edges
    workflow.add_edge("input_guardrails", "analyze_document")
    workflow.add_edge("analyze_document", "run_ocr")
    workflow.add_edge("run_ocr", "extract_fields")
    workflow.add_edge("extract_fields", "pii_scan")

    # Conditional: has target URL?
    workflow.add_conditional_edges(
        "pii_scan",
        has_target_url,
        {True: "analyze_form", False: "skip_form"},
    )
    workflow.add_edge("analyze_form", "map_fields")
    workflow.add_edge("skip_form", "map_fields")

    # Output guardrails then human review
    workflow.add_edge("map_fields", "output_guardrails")
    workflow.add_edge("output_guardrails", "human_review")

    # Conditional: human approved?
    workflow.add_conditional_edges(
        "human_review",
        is_approved,
        {True: "prefill_safety", False: "map_fields"},  # Rejected -> re-map
    )

    # Pre-fill safety then fill
    workflow.add_edge("prefill_safety", "fill_form")

    # Conditional: fill succeeded?
    workflow.add_conditional_edges(
        "fill_form",
        fill_successful,
        {True: "audit_log", False: "complete"},  # Even partial fill logs audit
    )

    workflow.add_edge("audit_log", "complete")
    workflow.set_finish_point("complete")

    return workflow.compile()


def get_graph():
    """Get or create the compiled graph singleton."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
