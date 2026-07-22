"""Tests for pre-fill safety checks."""

from __future__ import annotations

import pytest

from security.prefill_safety import PrefillSafety


@pytest.mark.asyncio
async def test_valid_url_passes():
    safety = PrefillSafety()
    result = await safety.check("https://example.com/form")
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_empty_url_fails():
    safety = PrefillSafety()
    result = await safety.check("")
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_unsupported_scheme_fails():
    safety = PrefillSafety()
    result = await safety.check("ftp://example.com/form")
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_destructive_url_blocked():
    safety = PrefillSafety()
    result = await safety.check("https://example.com/delete-account")
    assert result["passed"] is False
    assert "destructive" in result["error"].lower()
