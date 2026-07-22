"""Pydantic schemas for API request/response."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    target_url: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    status: str
    doc_type: str | None = None
    doc_quality: str | None = None
    ocr_strategy: str | None = None
    fill_status: str | None = None
    total_cost_usd: float = 0.0
    created_at: str | None = None
    completed_at: str | None = None


class ReviewData(BaseModel):
    extracted_fields: dict[str, Any] = {}
    form_fields: list[dict[str, Any]] = []
    field_mappings: dict[str, Any] = {}
    unmapped_fields: list[str] = []


class ReviewSubmission(BaseModel):
    corrections: dict[str, Any] = {}
    mappings: dict[str, Any] = {}
    action: str = "approve"  # "approve" | "reject"
    reason: str | None = None


class SearchQuery(BaseModel):
    q: str = Field(min_length=1)
    doc_type: str | None = None
    limit: int = 20


class SearchResult(BaseModel):
    session_id: str
    doc_type: str | None = None
    extracted_fields: dict[str, Any] = {}
    similarity: float = 0.0
    created_at: str | None = None


class RouteOverride(BaseModel):
    route: str | None = None
    provider: str | None = None
    model: str | None = None


class ProviderToggle(BaseModel):
    provider_name: str
    enabled: bool


class StrategyOverride(BaseModel):
    strategy: str
    route: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    ocr_backends: dict[str, bool] = {}
    db_connected: bool = False
    gateway_available: bool = False
