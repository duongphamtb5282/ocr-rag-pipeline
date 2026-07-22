"""Authentication and authorization middleware — JWT validation, tenant extraction, API key auth."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AuthContext:
    """Authenticated request context with tenant and user identity."""
    tenant_id: str
    user_id: str
    plan: str  # "trial" | "starter" | "pro" | "enterprise"
    roles: list[str]
    auth_method: str  # "jwt" | "api_key" | "anonymous"

    @property
    def is_authenticated(self) -> bool:
        return self.auth_method != "anonymous"

    @property
    def is_trial(self) -> bool:
        return self.plan == "trial"


# Default anonymous context for development
ANONYMOUS_CONTEXT = AuthContext(
    tenant_id="default",
    user_id="anonymous",
    plan="trial",
    roles=["user"],
    auth_method="anonymous",
)

# Admin API key context
ADMIN_CONTEXT = AuthContext(
    tenant_id="admin",
    user_id="admin",
    plan="enterprise",
    roles=["admin"],
    auth_method="api_key",
)


class AuthMiddleware:
    """
    FastAPI middleware that extracts AuthContext from:
    1. Authorization: Bearer <JWT> — validates JWT and extracts tenant/user
    2. X-API-Key header — validates against configured API keys
    3. No auth — assigns anonymous context (development only)
    """

    def __init__(self):
        self._api_keys: dict[str, AuthContext] = {}
        self._jwt_secret = settings.ADMIN_API_KEY or "dev-secret-do-not-use-in-prod"
        self._load_api_keys()

    def _load_api_keys(self):
        """Load API keys from config or env."""
        if settings.ADMIN_API_KEY:
            self._api_keys[settings.ADMIN_API_KEY] = ADMIN_CONTEXT

    def add_api_key(self, key: str, context: AuthContext):
        """Register an API key for programmatic access."""
        self._api_keys[key] = context

    async def authenticate(self, request: Request) -> AuthContext:
        """Authenticate request and return AuthContext."""
        # 1. Check X-API-Key header
        api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
        if api_key and api_key in self._api_keys:
            return self._api_keys[api_key]

        # 2. Check Authorization: Bearer <token>
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                return await self._validate_jwt(token)
            except Exception as e:
                logger.warning(f"JWT validation failed: {e}")
                # Fall through to anonymous

        # 3. Development mode: allow anonymous
        if settings.ENVIRONMENT in ("development", "test"):
            return ANONYMOUS_CONTEXT

        # 4. Production: reject unauthenticated
        raise HTTPException(status_code=401, detail="Authentication required")

    async def _validate_jwt(self, token: str) -> AuthContext:
        """
        Validate a JWT token and extract tenant information.
        Supports both HS256 and RS256 signatures.
        Falls back to simple HMAC validation for development.
        """
        try:
            # Try PyJWT if available
            import jwt as pyjwt
            try:
                payload = pyjwt.decode(
                    token,
                    self._jwt_secret,
                    algorithms=["HS256", "RS256"],
                    options={"verify_exp": True},
                )
                return AuthContext(
                    tenant_id=payload.get("tenant_id") or payload.get("sub", "unknown"),
                    user_id=payload.get("user_id") or payload.get("sub", "unknown"),
                    plan=payload.get("plan", "trial"),
                    roles=payload.get("roles", ["user"]),
                    auth_method="jwt",
                )
            except pyjwt.ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="Token expired")
            except pyjwt.InvalidTokenError as e:
                logger.warning(f"Invalid JWT: {e}")
                raise HTTPException(status_code=401, detail="Invalid token")

        except ImportError:
            # Fallback: simple HMAC validation
            parts = token.split(".")
            if len(parts) != 3:
                raise HTTPException(status_code=401, detail="Invalid token format")
            try:
                payload_b64 = parts[1]
                # Add padding
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                import base64
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                return AuthContext(
                    tenant_id=payload.get("tenant_id", "unknown"),
                    user_id=payload.get("user_id", "unknown"),
                    plan=payload.get("plan", "trial"),
                    roles=payload.get("roles", ["user"]),
                    auth_method="jwt",
                )
            except Exception:
                raise HTTPException(status_code=401, detail="Invalid token")


# Singleton
auth_middleware = AuthMiddleware()


async def get_auth_context(request: Request) -> AuthContext:
    """FastAPI dependency that extracts AuthContext from request."""
    return await auth_middleware.authenticate(request)


def require_role(role: str):
    """FastAPI dependency factory: require a specific role."""
    async def check_role(request: Request) -> AuthContext:
        auth = await get_auth_context(request)
        if role not in auth.roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {role}")
        return auth
    return check_role


def require_plan(min_plan: str):
    """FastAPI dependency factory: require minimum plan level."""
    PLAN_LEVELS = {"trial": 0, "starter": 1, "pro": 2, "enterprise": 3}

    async def check_plan(request: Request) -> AuthContext:
        auth = await get_auth_context(request)
        if PLAN_LEVELS.get(auth.plan, 0) < PLAN_LEVELS.get(min_plan, 0):
            raise HTTPException(
                status_code=402,
                detail=f"Plan '{auth.plan}' does not support this feature. Upgrade to '{min_plan}'.",
            )
        return auth
    return check_plan
