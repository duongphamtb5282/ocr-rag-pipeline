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

    # ── LLM Provider selection (Factory — one active provider at a time) ──
    # The LLMProviderFactory instantiates exactly one adapter for this provider.
    # The auto-switcher may flip it at runtime (outage/budget) — still one at a time.
    LLM_PROVIDER: Literal["openai", "anthropic", "azure", "bedrock", "deepseek", "google", "local"] = "openai"

    # ── LLM Providers ──
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""

    # ── Azure AI (Azure OpenAI) ──
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""          # e.g. https://my-resource.openai.azure.com/
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"
    # Azure calls the model by its *deployment name* — map logical model ids to deployments:
    AZURE_OPENAI_DEPLOYMENT_CHAT: str = "gpt-4o"                    # chat + vision (GPT-4o family)
    AZURE_OPENAI_DEPLOYMENT_CHAT_MINI: str = "gpt-4o-mini"          # cheap classification/mapping
    AZURE_OPENAI_DEPLOYMENT_EMBEDDING_LARGE: str = "text-embedding-3-large"
    AZURE_OPENAI_DEPLOYMENT_EMBEDDING_SMALL: str = "text-embedding-3-small"

    # ── DeepSeek (per ADR-0006 — OpenAI-compatible endpoint) ──
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_VISION_ENABLED: bool = False      # experimental vision-exp off by default (TO-7)
    DEEPSEEK_PII_POLICY: Literal["allow", "block-sensitive"] = "block-sensitive"  # TO-9 gate

    # ── AWS Bedrock (per ADR-0002 — adapter pending build) ──
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_BEDROCK_ENABLED: bool = False

    # ── Gateway ──
    LLM_GATEWAY_STRATEGY: Literal["cost_optimized", "quality_optimized", "balanced", "manual"] = "balanced"
    LLM_DAILY_BUDGET_USD: float = 25.0       # ADR-0003: startup ceiling $500/mo → $25/day
    LLM_MONTHLY_BUDGET_USD: float = 500.0    # ADR-0003: hard ceiling
    LLM_MAX_PER_SESSION_USD: float = 0.15    # ADR-0003: reconciled per-session cap

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
