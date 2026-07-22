"""Provider registry — all supported LLM providers and models."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    provider: str
    model_id: str
    priority: int
    cost_input: float
    cost_output: float
    capabilities: list[str] = field(default_factory=list)


class CircuitBreaker:
    """Per-provider circuit breaker: CLOSED -> OPEN -> HALF_OPEN."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_s: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_s
        self.last_failure_time = 0.0
        self.state = "closed"

    def record_success(self):
        self.failure_count = 0
        if self.state == "half_open":
            self.state = "closed"
            logger.info("Circuit breaker recovered: CLOSED")

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = __import__("time").monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker OPEN: {self.failure_count} consecutive failures")

    def is_open(self) -> bool:
        if self.state == "open":
            if __import__("time").monotonic() - self.last_failure_time > self.recovery_timeout:
                self.state = "half_open"
                return False
            return True
        return False


class ProviderRegistry:
    """Config-driven registry of all available LLM providers and models."""

    def __init__(self):
        self._providers: dict[str, dict] = {}
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._load_default_config()

    def _load_default_config(self):
        """Load provider config from settings."""
        self._providers = {
            "openai": {
                "enabled": bool(settings.OPENAI_API_KEY),
                "priority": 1,
                "models": [
                    {"id": "gpt-4o",             "capabilities": ["vision", "extraction", "classification"], "cost_input": 0.005,  "cost_output": 0.015},
                    {"id": "gpt-4o-mini",         "capabilities": ["classification", "mapping"],             "cost_input": 0.00015, "cost_output": 0.0006},
                    {"id": "text-embedding-3-large", "capabilities": ["embedding"],                           "cost_input": 0.00013, "cost_output": 0.0},
                    {"id": "text-embedding-3-small", "capabilities": ["embedding"],                           "cost_input": 0.00002, "cost_output": 0.0},
                ],
            },
            "anthropic": {
                "enabled": bool(settings.ANTHROPIC_API_KEY),
                "priority": 2,
                "models": [
                    {"id": "claude-sonnet-4-20250514", "capabilities": ["vision", "extraction", "classification"], "cost_input": 0.003, "cost_output": 0.015},
                    {"id": "claude-haiku-4-20251001",  "capabilities": ["classification", "mapping"],              "cost_input": 0.00025, "cost_output": 0.00125},
                ],
            },
        }
        self._circuit_breakers = {
            name: CircuitBreaker() for name in self._providers
        }

    def get_available_models(self, capability: str, budget_tier: str = "any") -> list[ModelInfo]:
        """Get models matching a capability, sorted by budget tier."""
        candidates = []
        for prov_name, prov_cfg in self._providers.items():
            if not prov_cfg["enabled"]:
                continue
            cb = self._circuit_breakers.get(prov_name)
            if cb and cb.is_open():
                continue
            for model in prov_cfg["models"]:
                if capability in model["capabilities"]:
                    candidates.append(ModelInfo(
                        provider=prov_name,
                        model_id=model["id"],
                        priority=prov_cfg["priority"],
                        cost_input=model["cost_input"],
                        cost_output=model["cost_output"],
                        capabilities=model["capabilities"],
                    ))
        if budget_tier == "cheapest":
            candidates.sort(key=lambda m: m.cost_input + m.cost_output)
        elif budget_tier == "best":
            candidates.sort(key=lambda m: m.priority)
        else:
            candidates.sort(key=lambda m: (m.priority, m.cost_input))
        return candidates

    def switch_provider_state(self, provider_name: str, enabled: bool):
        if provider_name in self._providers:
            self._providers[provider_name]["enabled"] = enabled
            logger.info(f"Provider {provider_name} {'enabled' if enabled else 'disabled'}")

    def record_failure(self, provider: str):
        cb = self._circuit_breakers.get(provider)
        if cb:
            cb.record_failure()

    def record_success(self, provider: str):
        cb = self._circuit_breakers.get(provider)
        if cb:
            cb.record_success()

    def get_stats(self) -> dict:
        return {
            name: {
                "enabled": cfg["enabled"],
                "circuit_breaker": self._circuit_breakers.get(name).state if self._circuit_breakers.get(name) else "closed",
                "models": [m["id"] for m in cfg["models"]],
            }
            for name, cfg in self._providers.items()
        }


registry = ProviderRegistry()
