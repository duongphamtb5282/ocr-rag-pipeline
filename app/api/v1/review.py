"""Human review endpoints — get review data, submit corrections."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas import ReviewData, ReviewSubmission
from app.db.database import get_session_factory
from app.models.session import SessionModel
from graph.builder import get_graph
from graph.state import create_initial_state
from security.audit_logger import audit_logger

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sessions/{session_id}/review", response_model=ReviewData)
async def get_review_data(session_id: str):
    """Get extracted fields and mappings pending human review."""
    factory = await get_session_factory()
    async with factory() as db:
        session = await db.get(SessionModel, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return ReviewData(
            extracted_fields=session.extracted_fields or {},
            form_fields=session.form_fields or [],
            field_mappings=session.field_mappings or {},
            unmapped_fields=[],
        )


@router.post("/sessions/{session_id}/review")
async def submit_review(session_id: str, review: ReviewSubmission):
    """Submit human review: corrections, mappings, and approval/rejection."""
    factory = await get_session_factory()
    async with factory() as db:
        session = await db.get(SessionModel, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if review.action == "approve":
            session.status = "awaiting_fill"
            session.human_corrections = review.corrections
            session.field_mappings = {**(session.field_mappings or {}), **review.mappings}
        elif review.action == "reject":
            session.status = "rejected"

        await db.commit()

    await audit_logger.log(
        f"review_{review.action}",
        session_id,
        {"correction_count": len(review.corrections), "mapping_count": len(review.mappings)},
    )

    return {"status": session.status}


@router.post("/sessions/{session_id}/process")
async def process_session(session_id: str):
    """Start processing a session through the LangGraph pipeline."""
    factory = await get_session_factory()
    async with factory() as db:
        session = await db.get(SessionModel, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

    # Create initial state and run graph
    state = create_initial_state(
        session_id=session_id,
        document_path=session.document_path or "",
        target_url=session.target_url,
        tenant_id=session.tenant_id or "default",
        user_id=session.user_id or "anonymous",
    )

    graph = get_graph()
    try:
        result = await graph.ainvoke(state)

        # Update session with results
        async with factory() as db:
            db_session = await db.get(SessionModel, session_id)
            if db_session:
                db_session.status = "awaiting_review" if result.get("review_status") == "pending" else "completed"
                db_session.doc_type = result.get("doc_type")
                db_session.doc_quality = result.get("doc_quality")
                db_session.ocr_strategy = result.get("ocr_strategy")
                db_session.extracted_fields = result.get("extracted_fields")
                db_session.field_mappings = result.get("field_mappings")
                db_session.form_fields = result.get("form_fields")
                db_session.fill_status = result.get("fill_status")
                db_session.submission_proof = result.get("submission_proof")
                await db.commit()

        return {"session_id": session_id, "status": result.get("review_status", "completed")}

    except Exception as e:
        logger.error(f"Graph execution failed for {session_id}: {e}")
        async with factory() as db:
            db_session = await db.get(SessionModel, session_id)
            if db_session:
                db_session.status = "failed"
                await db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
