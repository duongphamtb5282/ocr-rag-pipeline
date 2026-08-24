"""Azure AI (Azure OpenAI) adapter — chat + embeddings via the OpenAI SDK.

Azure calls models by their *deployment name* (configured in the Azure portal),
not by the model id. This adapter maps the registry's logical model ids
(gpt-4o, gpt-4o-mini, text-embedding-3-*) to deployment names via env config.

Enabled when AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT are set.
Select it as the single active provider with LLM_PROVIDER=azure (see factory.py).
"""

from __future__ import annotations

import logging

from openai import AsyncAzureOpenAI

from app.config import settings
from app.gateway.adapters.base import LLMProviderAdapter

logger = logging.getLogger(__name__)

# Logical model id -> Azure deployment name (env-overridable).
_DEPLOYMENT_MAP: dict[str, str] = {
    "gpt-4o":                 "AZURE_OPENAI_DEPLOYMENT_CHAT",
    "gpt-4o-mini":            "AZURE_OPENAI_DEPLOYMENT_CHAT_MINI",
    "text-embedding-3-large": "AZURE_OPENAI_DEPLOYMENT_EMBEDDING_LARGE",
    "text-embedding-3-small": "AZURE_OPENAI_DEPLOYMENT_EMBEDDING_SMALL",
}


def _deployment_for(model: str) -> str | None:
    """Resolve a registry model id to an Azure deployment name."""
    env_key = _DEPLOYMENT_MAP.get(model)
    if env_key is None:
        # Fall back to the chat deployment — vision and custom models reuse it.
        return getattr(settings, "AZURE_OPENAI_DEPLOYMENT_CHAT", "") or None
    return getattr(settings, env_key, "") or None


class AzureOpenAIAdapter(LLMProviderAdapter):
    """Azure AI (Azure OpenAI) adapter — chat + vision + embeddings."""

    supports_embedding: bool = True

    def __init__(self):
        self.client = None
        if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
            )

    @property
    def available(self) -> bool:
        return self.client is not None

    async def invoke(self, model: str, messages: list, max_tokens: int = 1024, temperature: float = 0.0) -> dict:
        if not self.client:
            raise RuntimeError("Azure OpenAI client not configured (AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT)")
        deployment = _deployment_for(model)
        if not deployment:
            raise RuntimeError(f"No Azure deployment configured for model: {model}")
        response = await self.client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return {
            "content": response.choices[0].message.content or "",
            "usage": {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        }

    async def embed(self, text: str, model: str = "text-embedding-3-large", dimensions: int = 1536) -> list[float]:
        if not self.client:
            raise RuntimeError("Azure OpenAI client not configured (AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT)")
        deployment = _deployment_for(model)
        if not deployment:
            raise RuntimeError(f"No Azure deployment configured for embedding model: {model}")
        response = await self.client.embeddings.create(
            model=deployment,
            input=text,
            dimensions=dimensions,
        )
        return response.data[0].embedding
