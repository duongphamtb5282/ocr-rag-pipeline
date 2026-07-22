"""OpenAI / Azure OpenAI adapter."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import settings
from app.gateway.adapters.base import LLMProviderAdapter

logger = logging.getLogger(__name__)


class OpenAIAdapter(LLMProviderAdapter):
    """OpenAI Direct adapter. Extend with Azure OpenAI via api_type config."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    @property
    def available(self) -> bool:
        return self.client is not None

    async def invoke(self, model: str, messages: list, max_tokens: int = 1024, temperature: float = 0.0) -> dict:
        if not self.client:
            raise RuntimeError("OpenAI client not configured")
        response = await self.client.chat.completions.create(
            model=model,
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
            raise RuntimeError("OpenAI client not configured")
        response = await self.client.embeddings.create(
            model=model,
            input=text,
            dimensions=dimensions,
        )
        return response.data[0].embedding
