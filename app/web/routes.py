"""Web UI routes — serves HTML pages for upload, review, and admin."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_dir)) if template_dir.exists() else None


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    """Upload page."""
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    return HTMLResponse("<html><body><h1>OCR Form Fill</h1><p>Web UI templates not loaded.</p></body></html>")


@router.get("/session/{session_id}", response_class=HTMLResponse, include_in_schema=False)
async def session_detail(request: Request, session_id: str):
    """Session detail with progress."""
    if templates:
        return templates.TemplateResponse("session.html", {"request": request, "session_id": session_id})
    return HTMLResponse(f"<html><body><h1>Session {session_id}</h1></body></html>")


@router.get("/review/{session_id}", response_class=HTMLResponse, include_in_schema=False)
async def review_page(request: Request, session_id: str):
    """Human review page."""
    if templates:
        return templates.TemplateResponse("review.html", {"request": request, "session_id": session_id})
    return HTMLResponse(f"<html><body><h1>Review {session_id}</h1></body></html>")


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(request: Request):
    """Admin panel."""
    if templates:
        return templates.TemplateResponse("admin.html", {"request": request})
    return HTMLResponse("<html><body><h1>Admin Panel</h1></body></html>")


@router.get("/history", response_class=HTMLResponse, include_in_schema=False)
async def history_page(request: Request):
    """Session history."""
    if templates:
        return templates.TemplateResponse("history.html", {"request": request})
    return HTMLResponse("<html><body><h1>Session History</h1></body></html>")


@router.get("/search", response_class=HTMLResponse, include_in_schema=False)
async def search_page(request: Request):
    """Semantic search page."""
    if templates:
        return templates.TemplateResponse("search.html", {"request": request})
    return HTMLResponse("<html><body><h1>Semantic Search</h1></body></html>")
