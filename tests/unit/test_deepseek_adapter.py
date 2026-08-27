"""Tests for the DeepSeek provider wiring (ADR-0006).

Covers the four wiring points from the ADR:
1. DeepSeekAdapter contract (invoke/embed/available/supports_embedding)
2. Registry: deepseek configured + enabled, models by capability
3. Telemetry: deepseek-* cost rows (without them the provider silently costs $0)
4. Factory: active adapter + embedding fallback when deepseek is active
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.gateway.adapters.base import LLMProviderAdapter
from app.gateway.adapters.deepseek_adapter import DeepSeekAdapter
from app.gateway.adapters.factory import LLMProviderFactory
from app.gateway.adapters.openai_adapter import OpenAIAdapter
from app.gateway.registry import ProviderRegistry
from app.gateway.telemetry import COST_PER_1K_TOKENS


# ── Fake OpenAI-compatible client (mirrors the AsyncOpenAI response shape) ──

class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 5


class _FakeMessage:
    content = "hello from deepseek"


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]
    usage = _FakeUsage()


class _FakeCompletions:
    def __init__(self, response):
        self._response = response

    async def create(self, **kwargs):
        return self._response


class _FakeChat:
    def __init__(self, response):
        self.completions = _FakeCompletions(response)


class _FakeClient:
    def __init__(self, response=None):
        self.chat = _FakeChat(response or _FakeResponse())


# ── Adapter contract ──

def test_supports_embedding_is_false():
    # DeepSeek has no embeddings endpoint (TO-8) — the factory must fall back.
    assert DeepSeekAdapter.supports_embedding is False


def test_adapter_is_llm_provider_adapter():
    assert issubclass(DeepSeekAdapter, LLMProviderAdapter)


def test_not_available_without_key(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    adapter = DeepSeekAdapter()
    assert adapter.available is False


def test_available_with_key(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    adapter = DeepSeekAdapter()
    assert adapter.available is True


async def test_invoke_returns_uniform_contract(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    adapter = DeepSeekAdapter()
    adapter.client = _FakeClient()
    result = await adapter.invoke(
        "deepseek-v4-flash",
        [{"role": "user", "content": "hi"}],
        max_tokens=1024,
        temperature=0.0,
    )
    assert result["content"] == "hello from deepseek"
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 5}


async def test_invoke_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    adapter = DeepSeekAdapter()
    with pytest.raises(RuntimeError, match="not configured"):
        await adapter.invoke("deepseek-v4-flash", [{"role": "user", "content": "hi"}])


async def test_embed_raises_not_implemented(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    adapter = DeepSeekAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.embed("hello", model="deepseek-v4-flash")


# ── Registry wiring ──

def _deepseek_registry(monkeypatch) -> ProviderRegistry:
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    return ProviderRegistry()


def test_registry_deepseek_configured_and_enabled(monkeypatch):
    reg = _deepseek_registry(monkeypatch)
    cfg = reg._providers["deepseek"]
    assert cfg["configured"] is True
    assert cfg["enabled"] is True


def test_registry_deepseek_not_enabled_when_not_selected(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    reg = ProviderRegistry()
    assert reg._providers["deepseek"]["configured"] is True
    assert reg._providers["deepseek"]["enabled"] is False


def test_registry_deepseek_models_by_capability(monkeypatch):
    reg = _deepseek_registry(monkeypatch)
    models = reg.get_available_models("classification")
    ids = {m.model_id for m in models}
    assert "deepseek-v4-flash" in ids
    assert "deepseek-v4-pro" in ids


def test_registry_deepseek_vision_model_flagged_experimental(monkeypatch):
    reg = _deepseek_registry(monkeypatch)
    models = reg.get_available_models("vision")
    assert any(m.model_id == "deepseek-v4-flash-vision-exp" for m in models)


def test_registry_deepseek_no_embedding_models(monkeypatch):
    reg = _deepseek_registry(monkeypatch)
    models = reg.get_available_models("embedding")
    assert not any(m.provider == "deepseek" for m in models)


# ── Telemetry cost rows ──

def test_telemetry_has_deepseek_cost_rows():
    # Without these rows the provider silently costs $0 (ADR-0002 §4 trap).
    assert "deepseek" in COST_PER_1K_TOKENS
    for model in ("deepseek-v4-flash", "deepseek-v4-pro", "deepseek-v4-flash-vision-exp"):
        assert model in COST_PER_1K_TOKENS["deepseek"]
        assert COST_PER_1K_TOKENS["deepseek"][model]["input"] > 0
        assert COST_PER_1K_TOKENS["deepseek"][model]["output"] > 0


# ── Factory wiring ──

def test_factory_active_adapter_is_deepseek(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    factory = LLMProviderFactory()
    adapter = factory.get_active_adapter()
    assert isinstance(adapter, DeepSeekAdapter)


def test_factory_embedding_falls_back_when_deepseek_active(monkeypatch):
    # DeepSeek has no embeddings — the factory must fall back to a configured
    # embed-capable provider (openai), same as the anthropic pattern.
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    factory = LLMProviderFactory()
    adapter = factory.get_embedding_adapter()
    assert isinstance(adapter, OpenAIAdapter)


def test_factory_embedding_returns_none_without_fallback(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    factory = LLMProviderFactory()
    assert factory.get_embedding_adapter() is None
