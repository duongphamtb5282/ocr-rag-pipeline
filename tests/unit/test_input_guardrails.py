"""Tests for input guardrails — document validation."""

from __future__ import annotations

import pytest

from guardrail.input_guard import InputGuard


@pytest.mark.asyncio
async def test_valid_pdf_passes(sample_pdf):
    guardrail = InputGuard()
    result = await guardrail.validate(str(sample_pdf))
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_nonexistent_file_fails():
    guardrail = InputGuard()
    result = await guardrail.validate("/nonexistent/file.pdf")
    assert result["passed"] is False
    assert result["flag"] == "missing_file"


@pytest.mark.asyncio
async def test_magic_byte_rejects_invalid(tmp_path):
    """A file with wrong magic bytes should be rejected."""
    f = tmp_path / "fake.pdf"
    f.write_bytes(b"This is not a PDF but has .pdf extension")
    guardrail = InputGuard()
    result = await guardrail.validate(str(f))
    assert result["passed"] is False
    assert result["flag"] == "invalid_file_type"


@pytest.mark.asyncio
async def test_file_too_large_fails(tmp_path):
    f = tmp_path / "large.pdf"
    f.write_bytes(b"%PDF" + b"x" * (InputGuard.MAX_FILE_SIZE_BYTES + 1))
    guardrail = InputGuard()
    result = await guardrail.validate(str(f))
    assert result["passed"] is False
    assert result["flag"] == "file_too_large"
