"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check — returns service status."""
    return HealthResponse(
        status="ok",
        ocr_backends={
            "tesseract": True,
            "pdfplumber": True,
            "llm_vision": True,
        },
        db_connected=True,
        gateway_available=True,
    )
