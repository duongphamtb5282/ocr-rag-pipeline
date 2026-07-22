"""Tests for authentication and authorization middleware."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth import AuthContext, AuthMiddleware, ANONYMOUS_CONTEXT


@pytest.mark.asyncio
async def test_anonymous_context_in_dev():
    """In development mode, unauthenticated requests get anonymous context."""
    auth = AuthMiddleware()
    # Create a mock request with no auth headers
    class MockRequest:
        headers = {}
        url = type("URL", (), {"path": "/api/v1/sessions"})()

    ctx = await auth.authenticate(MockRequest())
    assert ctx.tenant_id == "default"
    assert ctx.auth_method == "anonymous"


def test_auth_context_properties():
    ctx = AuthContext(tenant_id="tenant-1", user_id="user-1", plan="pro", roles=["user", "admin"], auth_method="jwt")
    assert ctx.is_authenticated is True
    assert ctx.is_trial is False


def test_trial_context():
    ctx = AuthContext(tenant_id="trial-1", user_id="user-1", plan="trial", roles=["user"], auth_method="api_key")
    assert ctx.is_trial is True


def test_anonymous_context():
    assert ANONYMOUS_CONTEXT.is_authenticated is False
    assert ANONYMOUS_CONTEXT.auth_method == "anonymous"
    assert ANONYMOUS_CONTEXT.plan == "trial"
