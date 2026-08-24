"""LLM provider factory — exactly one active adapter at a time.

The factory owns adapter instantiation. The active provider is selected by the
LLM_PROVIDER env var (see app/config.py). All gateway calls resolve through
get_active_adapter(); the auto-switcher may flip the active provider at runtime
(outage / budget), but only one adapter is ever instantiated and served.

Embedding note: only providers with an embedding model implement embed().
When the active provider has none (e.g. anthropic), gateway_embed falls back to
the OpenAI adapter if configured — the pipeline needs embeddings for vector
search regardless of which provider serves chat (per D-5 in the trade-off doc).
"""

from __future__ import annotations

import logging

from app.config import settings
from app.gateway.adapters.anthropic_adapter import AnthropicAdapter
from app.gateway.adapters.azure_adapter import AzureOpenAIAdapter
from app.gateway.adapters.base import LLMProviderAdapter
from app.gateway.adapters.openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)

# Provider name (LLM_PROVIDER value) -> adapter class.
_ADAPTER_CLASSES: dict[str, type[LLMProviderAdapter]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "azure": AzureOpenAIAdapter,
    # "bedrock": BedrockAdapter,   # ADR-0002 — pending build (needs boto3)
    # "google": GoogleVertexAdapter,  # pending
    # "local": LocalAdapter,          # pending (Ollama / vLLM)
}


class LLMProviderFactory:
    """Builds and caches adapter instances; resolves the single active provider."""

    def __init__(self):
        self._adapters: dict[str, LLMProviderAdapter] = {}

    def get_adapter(self, provider: str) -> LLMProviderAdapter | None:
        """Return a configured adapter for provider, or None if unavailable."""
        adapter_class = _ADAPTER_CLASSES.get(provider)
        if adapter_class is None:
            logger.warning(f"No adapter registered for provider: {provider}")
            return None
        if provider not in self._adapters:
            adapter = adapter_class()
            if not adapter.available:
                logger.warning(
                    f"Provider '{provider}' selected but not configured "
                    f"(missing API key / endpoint) — check env"
                )
                return None
            self._adapters[provider] = adapter
            logger.info(f"Factory instantiated adapter: {provider}")
        return self._adapters[provider]

    def get_active_adapter(self) -> LLMProviderAdapter | None:
        """Return the adapter for settings.LLM_PROVIDER (one at a time)."""
        return self.get_adapter(settings.LLM_PROVIDER)

    def get_embedding_adapter(self) -> LLMProviderAdapter | None:
        """Active adapter if it can embed; otherwise a configured embed-capable provider."""
        active = self.get_active_adapter()
        if active is not None and active.supports_embedding:
            return active
        # Fallback: any configured adapter that supports embeddings (openai/azure).
        for provider, adapter_class in _ADAPTER_CLASSES.items():
            if provider == settings.LLM_PROVIDER or not adapter_class.supports_embedding:
                continue
            adapter = self.get_adapter(provider)
            if adapter is not None:
                return adapter
        return None


provider_factory = LLMProviderFactory()
