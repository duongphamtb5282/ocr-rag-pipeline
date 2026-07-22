"""Anthropic / AWS Bedrock adapter."""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from app.config import settings
from app.gateway.adapters.base import LLMProviderAdapter

logger = logging.getLogger(__name__)


class AnthropicAdapter(LLMProviderAdapter):
    """Anthropic Direct adapter."""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None

    @property
    def available(self) -> bool:
        return self.client is not None

    async def invoke(self, model: str, messages: list, max_tokens: int = 1024, temperature: float = 0.0) -> dict:
        if not self.client:
            raise RuntimeError("Anthropic client not configured")
        response = await self.client.messages.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return {
            "content": response.content[0].text if response.content else "",
            "usage": {
                "input_tokens": response.usage.input_tokens if response.usage else 0,
                "output_tokens": response.usage.output_tokens if response.usage else 0,
            },
        }

    async def embed(self, text: str, model: str = "", dimensions: int = 1536) -> list[float]:
        raise NotImplementedError("Anthropic does not provide embedding models")
