"""Tests for abuse detection."""

from __future__ import annotations

import pytest

from security.abuse_detector import AbuseDetector


@pytest.mark.asyncio
async def test_first_upload_allowed():
    detector = AbuseDetector()
    result = await detector.check_upload_allowed("user-1", "tenant-1")
    assert result["allowed"] is True


@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    detector = AbuseDetector()
    # Simulate many rapid uploads
    for _ in range(100):
        await detector.check_upload_allowed("user-fast", "tenant-1")
    result = await detector.check_upload_allowed("user-fast", "tenant-1")
    assert result["allowed"] is False
    assert result["reason"] == "rate_limit_exceeded"
