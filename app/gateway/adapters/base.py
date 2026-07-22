"""Abstract base class for LLM provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProviderAdapter(ABC):
    """Abstract base for all LLM provider adapters."""

    @abstractmethod
    async def invoke(self, model: str, messages: list, max_tokens: int = 1024, temperature: float = 0.0) -> dict:
        """Call the LLM and return response with content and usage."""
        ...

    @abstractmethod
    async def embed(self, text: str, model: str, dimensions: int = 1536) -> list[float]:
        """Generate embedding vector for text."""
        ...
