"""DeepSeek (V4) adapter — OpenAI-compatible endpoint (ADR-0006).

DeepSeek's API (api.deepseek.com) speaks the OpenAI wire format, so this
adapter is the OpenAI SDK with a base-url override. Capability notes:
- Chat: deepseek-v4-flash (default), deepseek-v4-pro (quality route).
- Vision: deepseek-v4-flash-vision-exp is EXPERIMENTAL (TO-7) — images are
  accepted in user messages only; system/assistant image blocks return 400.
- Embeddings: DeepSeek has NO embeddings endpoint (TO-8) — supports_embedding
  is False so the factory falls back to a configured embed-capable provider
  (openai/azure), the same mechanism the anthropic adapter relies on.
"""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import settings
from app.gateway.adapters.base import LLMProviderAdapter

logger = logging.getLogger(__name__)


class DeepSeekAdapter(LLMProviderAdapter):
    """DeepSeek direct API (api.deepseek.com). OpenAI-compatible wire format."""

    supports_embedding: bool = False  # DeepSeek has no embeddings endpoint (TO-8)

    def __init__(self):
        self.client = (
            AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
            if settings.DEEPSEEK_API_KEY
            else None
        )

    @property
    def available(self) -> bool:
        return self.client is not None

    async def invoke(self, model: str, messages: list, max_tokens: int = 1024, temperature: float = 0.0) -> dict:
        if not self.client:
            raise RuntimeError("DeepSeek client not configured (DEEPSEEK_API_KEY)")
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

    async def embed(self, text: str, model: str = "", dimensions: int = 1536) -> list[float]:
        raise NotImplementedError(
            "DeepSeek has no embeddings endpoint — the factory falls back to OpenAI/Azure (TO-8)"
        )
