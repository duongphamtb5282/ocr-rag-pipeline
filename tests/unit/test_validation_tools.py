"""Tests for validation tools."""

from __future__ import annotations

from tools.validation import ValidationTools


def test_date_validation_iso():
    result = ValidationTools.validate_date("2024-01-15")
    assert result["valid"] is True
    assert result["format"] == "ISO"


def test_date_validation_us():
    result = ValidationTools.validate_date("01/15/2024")
    assert result["valid"] is True
    assert result["format"] == "US"


def test_date_validation_invalid():
    result = ValidationTools.validate_date("not-a-date")
    assert result["valid"] is False


def test_phone_validation_e164():
    result = ValidationTools.validate_phone("+14155551234")
    assert result["valid"] is True


def test_phone_validation_with_dashes():
    result = ValidationTools.validate_phone("+1-415-555-1234")
    assert result["valid"] is True


def test_email_validation_valid():
    result = ValidationTools.validate_email("test@example.com")
    assert result["valid"] is True


def test_email_validation_invalid():
    result = ValidationTools.validate_email("not-an-email")
    assert result["valid"] is False


def test_currency_normalization():
    result = ValidationTools.normalize_currency("$1,249.99")
    assert result["valid"] is True
    assert result["value"] == 1249.99
