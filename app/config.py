"""Application configuration via pydantic-settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings loaded from environment variables / .env file."""

    # ── Environment ──
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # ── LLM Providers ──
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""

    # ── Gateway ──
    LLM_GATEWAY_STRATEGY: Literal["cost_optimized", "quality_optimized", "balanced", "manual"] = "balanced"
    LLM_DAILY_BUDGET_USD: float = 100.0
    LLM_MONTHLY_BUDGET_USD: float = 2500.0
    LLM_MAX_PER_SESSION_USD: float = 0.50

    # ── Database ──
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/sessions.db"

    # ── Vector DB ──
    VECTOR_DB_TYPE: Literal["memory", "qdrant", "pgvector"] = "memory"
    VECTOR_DB_URL: str = ""
    VECTOR_DB_API_KEY: str = ""

    # ── Redis ──
    REDIS_URL: str = ""

    # ── OCR ──
    OCR_DEFAULT_STRATEGY: Literal["auto", "tesseract", "doctr", "llm_vision", "pdfplumber"] = "auto"
    OCR_TESSERACT_CMD: str = "tesseract"

    # ── File Upload ──
    MAX_UPLOAD_SIZE_MB: int = 20
    MAX_PAGE_COUNT: int = 50
    UPLOAD_DIR: str = "./uploads"
    SCREENSHOT_DIR: str = "./screenshots"

    # ── Retention ──
    RETENTION_COMPLETED_DAYS: int = 30
    RETENTION_FAILED_DAYS: int = 7
    RETENTION_ABANDONED_DAYS: int = 1

    # ── Admin ──
    ADMIN_API_KEY: str = ""

    @property
    def upload_path(self) -> Path:
        return Path(self.UPLOAD_DIR)

    @property
    def screenshot_path(self) -> Path:
        return Path(self.SCREENSHOT_DIR)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
