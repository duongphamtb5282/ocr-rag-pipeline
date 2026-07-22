"""Tests for PII scanner."""

from __future__ import annotations

from security.pii_scanner import PIIScanner


async def test_pii_detects_ssn():
    scanner = PIIScanner()
    fields = {"tax_id": {"value": "123-45-6789"}}
    result = await scanner.scan_fields(fields)
    assert result["has_pii"] is True
    assert any(f["type"] == "ssn" for f in result["findings"])


async def test_pii_detects_credit_card():
    scanner = PIIScanner()
    fields = {"payment": {"value": "4111-1111-1111-1111"}}
    result = await scanner.scan_fields(fields)
    assert result["has_pii"] is True
    assert any(f["type"] == "credit_card" for f in result["findings"])


async def test_pii_detects_email():
    scanner = PIIScanner()
    fields = {"contact": {"value": "john.doe@example.com"}}
    result = await scanner.scan_fields(fields)
    assert result["has_pii"] is True
    assert any(f["type"] == "email" for f in result["findings"])


async def test_clean_data_no_pii():
    scanner = PIIScanner()
    fields = {"name": {"value": "John Doe"}, "amount": {"value": "42"}}
    result = await scanner.scan_fields(fields)
    assert result["has_pii"] is False


async def test_masking_ssn():
    scanner = PIIScanner()
    fields = {"ssn": {"value": "123-45-6789"}}
    result = await scanner.scan_fields(fields)
    assert result["findings"][0]["masked"] == "***6789"
