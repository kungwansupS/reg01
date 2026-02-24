"""
JWT / RBAC Authentication Module
================================
Replaces static ADMIN_TOKEN / DEV_TOKEN with JWT-based auth.

Backward-compatible: if AUTH_MODE=legacy (default), the old X-Admin-Token
and X-Dev-Token headers still work. Set AUTH_MODE=jwt to enforce JWT.

Roles: admin, dev, user
"""

import os
import time
import logging
from enum import Enum
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.api_key import APIKeyHeader
from passlib.hash import bcrypt

logger = logging.getLogger("Auth")

# ─── Configuration ───────────────────────────────────────────────────────────

AUTH_MODE = os.getenv("AUTH_MODE", "legacy")  # "legacy" | "jwt"
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "your-university-sso-secret")
AUTH_ALGORITHM = "HS256"
AUTH_TOKEN_EXPIRE_SECONDS = int(os.getenv("AUTH_TOKEN_EXPIRE_SECONDS", "86400"))  # 24h

# Legacy tokens (backward compat)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "super-secret-key")
DEV_TOKEN = os.getenv("DEV_TOKEN", "dev-secret-key")


class Role(str, Enum):
    admin = "admin"
    dev = "dev"
    user = "user"


# ─── JWT Helpers ─────────────────────────────────────────────────────────────

def create_jwt(subject: str, role: Role, extra: dict | None = None) -> str:
    """Create a signed JWT token."""
    now = int(time.time())
    payload = {
        "sub": subject,
        "role": role.value,
        "iat": now,
        "exp": now + AUTH_TOKEN_EXPIRE_SECONDS,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, AUTH_SECRET_KEY, algorithm=AUTH_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT token. Raises on invalid/expired."""
    try:
        return jwt.decode(token, AUTH_SECRET_KEY, algorithms=[AUTH_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ─── Password Hashing ───────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.verify(password, hashed)


# ─── FastAPI Dependencies ────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)
_admin_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)
_dev_key_header = APIKeyHeader(name="X-Dev-Token", auto_error=False)


async def _extract_jwt_claims(
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[dict]:
    """Extract JWT claims from Authorization: Bearer header."""
    if bearer and bearer.credentials:
        try:
            return decode_jwt(bearer.credentials)
        except HTTPException:
            # In legacy mode, allow non-JWT bearer values to fall back to
            # static token headers for backward compatibility.
            if AUTH_MODE == "legacy":
                return None
            raise
    return None


async def require_admin(
    request: Request,
    claims: Optional[dict] = Depends(_extract_jwt_claims),
    legacy_token: Optional[str] = Depends(_admin_key_header),
) -> dict:
    """
    Require admin-level access.

    JWT mode: checks 'role' in JWT claims == 'admin'.
    Legacy mode: checks X-Admin-Token header.
    """
    # JWT path
    if claims:
        if claims.get("role") != Role.admin.value:
            raise HTTPException(status_code=403, detail="Admin role required")
        return claims

    # Legacy path
    if AUTH_MODE == "legacy" and legacy_token:
        if legacy_token == ADMIN_TOKEN:
            return {"sub": "legacy-admin", "role": "admin"}
        raise HTTPException(status_code=403, detail="Invalid admin token")

    raise HTTPException(status_code=401, detail="Authentication required")


async def require_dev(
    request: Request,
    claims: Optional[dict] = Depends(_extract_jwt_claims),
    legacy_token: Optional[str] = Depends(_dev_key_header),
    legacy_admin_token: Optional[str] = Depends(_admin_key_header),
) -> dict:
    """
    Require dev-level access (admin also has dev access).
    """
    # JWT path
    if claims:
        if claims.get("role") not in (Role.admin.value, Role.dev.value):
            raise HTTPException(status_code=403, detail="Dev role required")
        return claims

    # Legacy path
    if AUTH_MODE == "legacy":
        if legacy_token:
            if legacy_token == DEV_TOKEN:
                return {"sub": "legacy-dev", "role": "dev"}
            raise HTTPException(status_code=403, detail="Invalid dev token")
        if legacy_admin_token:
            if legacy_admin_token == ADMIN_TOKEN:
                return {"sub": "legacy-admin", "role": "admin"}
            raise HTTPException(status_code=403, detail="Invalid admin token")

    raise HTTPException(status_code=401, detail="Authentication required")


async def require_user(
    request: Request,
    claims: Optional[dict] = Depends(_extract_jwt_claims),
) -> dict:
    """
    Require any authenticated user. Falls back to anonymous in legacy mode.
    """
    if claims:
        return claims

    if AUTH_MODE == "legacy":
        return {"sub": "anonymous", "role": "user"}

    raise HTTPException(status_code=401, detail="Authentication required")


# ─── Auth Endpoints (mount on the app) ───────────────────────────────────────

from fastapi import APIRouter, Form

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
):
    """
    Login endpoint. Returns a JWT token.

    In legacy mode, accepts ADMIN_TOKEN or DEV_TOKEN as the password with
    username 'admin' or 'dev' respectively.
    """
    # Legacy token login
    if username == "admin" and password == ADMIN_TOKEN:
        token = create_jwt(subject="admin", role=Role.admin)
        return {"access_token": token, "token_type": "bearer", "role": "admin"}

    if username == "dev" and password == DEV_TOKEN:
        token = create_jwt(subject="dev", role=Role.dev)
        return {"access_token": token, "token_type": "bearer", "role": "dev"}

    # TODO: Add real user database lookup here for SSO/OIDC integration
    raise HTTPException(status_code=401, detail="Invalid credentials")


@auth_router.get("/me")
async def get_current_user(claims: dict = Depends(require_user)):
    """Return current user info from JWT claims."""
    return {
        "sub": claims.get("sub"),
        "role": claims.get("role"),
    }
