"""Tests for budget controller."""

from __future__ import annotations

import pytest

from app.config import settings
from app.gateway.budget import BudgetController


@pytest.mark.asyncio
async def test_budget_allows_normal_call():
    controller = BudgetController()
    result = controller.check_call_budget("doc_classification", 0.001, "session-1", "normal")
    assert result.allowed is True


@pytest.mark.asyncio
async def test_budget_blocks_when_exhausted():
    controller = BudgetController()
    # Spend all daily budget
    controller._daily_spent = settings.LLM_DAILY_BUDGET_USD
    result = controller.check_call_budget("vision_ocr", 0.01, "session-1")
    assert result.allowed is False
    assert result.reason == "daily_hard_limit_reached"


@pytest.mark.asyncio
async def test_session_budget_enforced():
    controller = BudgetController()
    # Spend session budget
    controller.record_spend("session-1", settings.LLM_MAX_PER_SESSION_USD)
    result = controller.check_call_budget("vision_ocr", 0.01, "session-1")
    assert result.allowed is False
    assert result.reason == "session_budget_exceeded"


@pytest.mark.asyncio
async def test_budget_tracks_session_spend():
    controller = BudgetController()
    controller.record_spend("session-1", 0.05)
    assert controller.session_spent("session-1") == 0.05
    assert controller.session_remaining("session-1") == pytest.approx(settings.LLM_MAX_PER_SESSION_USD - 0.05, 0.01)
