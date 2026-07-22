"""Tests for output guardrails — field validation and injection protection."""

from __future__ import annotations

import pytest

from security.output_filter import OutputFilter


@pytest.mark.asyncio
async def test_clean_fields_pass():
    guardrail = OutputFilter()
    extracted = {"name": {"value": "John Doe"}}
    mappings = {"name": {"form_field_id": "full_name"}}
    form_fields = [{"field_id": "full_name", "type": "text"}]
    result = await guardrail.validate_all(extracted, mappings, form_fields)
    assert result["all_passed"] is True
    assert result["injection_detected"] is False


@pytest.mark.asyncio
async def test_xss_injection_detected():
    guardrail = OutputFilter()
    extracted = {"name": {"value": "<script>alert('xss')</script>"}}
    mappings = {"name": {"form_field_id": "full_name"}}
    form_fields = [{"field_id": "full_name", "type": "text"}]
    result = await guardrail.validate_all(extracted, mappings, form_fields)
    assert result["injection_detected"] is True
    assert any("xss" in str(i) for i in result["issues"])


@pytest.mark.asyncio
async def test_sql_injection_detected():
    guardrail = OutputFilter()
    extracted = {"name": {"value": "'; DROP TABLE users; --"}}
    mappings = {"name": {"form_field_id": "full_name"}}
    form_fields = [{"field_id": "full_name", "type": "text"}]
    result = await guardrail.validate_all(extracted, mappings, form_fields)
    assert result["injection_detected"] is True
    assert any("sql_injection" in str(i) for i in result["issues"])


@pytest.mark.asyncio
async def test_email_format_validation():
    guardrail = OutputFilter()
    extracted = {"email": {"value": "not-an-email"}}
    mappings = {"email": {"form_field_id": "user_email"}}
    form_fields = [{"field_id": "user_email", "type": "email"}]
    result = await guardrail.validate_all(extracted, mappings, form_fields)
    assert result["all_passed"] is False
