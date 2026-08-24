"""Session management endpoints."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from app.api.v1.schemas import SessionResponse
from app.auth import AuthContext, get_auth_context
from app.config import settings
from app.db.database import get_session_factory
from app.models.session import SessionModel
from app.ocr.toolbox import ocr_toolbox
from app.vector.dedup import duplicate_detector
from graph.state import create_initial_state
from guardrail.abuse_detector import abuse_detector
from guardrail.audit_logger import audit_logger
from guardrail.input_guard import input_guard as input_guardrails
from guardrail.data_retention import data_retention

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/sessions", status_code=201, response_model=SessionResponse)
async def create_session(file: UploadFile, request: Request, target_url: str | None = None, auth: AuthContext = Depends(get_auth_context)):
    """Upload a document and optionally specify a target URL for form filling."""
    session_id = str(uuid.uuid4())
    user_id = auth.user_id
    tenant_id = auth.tenant_id

    # 1. Save uploaded file
    ext = Path(file.filename or "upload").suffix if file.filename else ".bin"
    file_path = Path(settings.UPLOAD_DIR) / f"{session_id}{ext}"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(str(file_path), "wb") as f:
        content = await file.read()
        await f.write(content)

    # 2. Input guardrails
    guardrail_result = await input_guardrails.validate(str(file_path))
    if not guardrail_result.get("passed"):
        await audit_logger.log("guardrail_blocked_input", session_id, {
            "reason": guardrail_result.get("error"),
            "filename": file.filename,
        })
        raise HTTPException(status_code=422, detail=guardrail_result.get("error"))

    # 3. Abuse check
    abuse_check = await abuse_detector.check_upload_allowed(user_id, tenant_id, target_url)
    if not abuse_check.get("allowed"):
        await audit_logger.log("abuse_blocked", session_id, {"reason": abuse_check.get("reason")})
        raise HTTPException(status_code=429, detail=f"Rate limit: {abuse_check.get('reason')}")

    # 4. Duplicate check (async, non-blocking)
    try:
        preview = await ocr_toolbox.extract(str(file_path), strategy="tesseract")
        dup = await duplicate_detector.check(str(file_path), preview.get("text", ""))
    except Exception:
        dup = {"is_duplicate": False}

    # 5. Create session in database
    factory = await get_session_factory()
    async with factory() as db:
        session = SessionModel(
            session_id=session_id,
            status="uploaded",
            target_url=target_url,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        db.add(session)
        await db.commit()

    # 6. Log upload event
    await audit_logger.log("document_uploaded", session_id, {
        "filename": file.filename,
        "size": len(content),
        "target_url": target_url,
        "is_duplicate": dup.get("is_duplicate"),
    })

    return SessionResponse(
        session_id=session_id,
        status="uploaded",
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(limit: int = 50):
    """List all sessions."""
    factory = await get_session_factory()
    async with factory() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(SessionModel).where(SessionModel.deleted_at.is_(None)).order_by(SessionModel.created_at.desc()).limit(limit)
        )
        sessions = result.scalars().all()
        return [SessionResponse(
            session_id=s.session_id,
            status=s.status,
            doc_type=s.doc_type,
            fill_status=s.fill_status,
            total_cost_usd=s.total_cost_usd or 0.0,
            created_at=s.created_at.isoformat() if s.created_at else None,
            completed_at=s.completed_at.isoformat() if s.completed_at else None,
        ) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session details."""
    factory = await get_session_factory()
    async with factory() as db:
        session = await db.get(SessionModel, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(
            session_id=session.session_id,
            status=session.status,
            doc_type=session.doc_type,
            doc_quality=session.doc_quality,
            ocr_strategy=session.ocr_strategy,
            fill_status=session.fill_status,
            total_cost_usd=session.total_cost_usd or 0.0,
            created_at=session.created_at.isoformat() if session.created_at else None,
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
        )


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str):
    """Cancel a running session."""
    factory = await get_session_factory()
    async with factory() as db:
        session = await db.get(SessionModel, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session.status = "cancelled"
        await db.commit()

    await audit_logger.log("session_cancelled", session_id)
    return {"status": "cancelled"}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete session data (GDPR right-to-deletion)."""
    await data_retention.delete_session_data(session_id, reason="user_request")
    return {"status": "deleted"}
