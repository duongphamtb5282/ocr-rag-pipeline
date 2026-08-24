"""Abstract base class for LLM provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProviderAdapter(ABC):
    """Abstract base for all LLM provider adapters."""

    # Whether this provider offers an embedding model. Providers without one
    # (e.g. anthropic) leave this False — gateway_embed then falls back to a
    # configured embed-capable provider via the factory (see factory.py).
    supports_embedding: bool = False

    @abstractmethod
    async def invoke(self, model: str, messages: list, max_tokens: int = 1024, temperature: float = 0.0) -> dict:
        """Call the LLM and return response with content and usage."""
        ...

    @abstractmethod
    async def embed(self, text: str, model: str, dimensions: int = 1536) -> list[float]:
        """Generate embedding vector for text."""
        ...
