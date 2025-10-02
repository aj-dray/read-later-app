"""JWT authentication utilities for FastAPI service."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta
from typing import Any
import jwt
from fastapi import HTTPException, Request


# === VARIABLES ===


SALT_BYTES = 32
PBKDF2_ITERATIONS = 100000
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


# === UTILITIES


def _get_secret() -> str:
    return ( os.getenv("BACKEND_SECRET")
        or "dev-secret"
    )


def create_jwt_token(user_id: str, username: str) -> str:
    """Create a JWT token for the given user."""
    now = datetime.utcnow()
    payload = {
        "user_id": user_id,
        "username": username,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def _decode_jwt_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        return None


def get_session(request: Request) -> dict[str, Any] | None:
    """Extract session from Authorization header with Bearer token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() != "bearer":
            return None
    except ValueError:
        return None

    payload = _decode_jwt_token(token)
    if not payload:
        return None

    return {
        "user_id": str(payload.get("user_id", "")),
        "username": str(payload.get("username", "")),
        "issued_at": int(payload.get("iat", 0)),
        "expires_at": int(payload.get("exp", 0)),
    }


def require_session(request: Request) -> dict[str, Any]:
    session = getattr(request.state, "session", None)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_hash = base64.b64encode(derived).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${encoded_salt}${encoded_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_str, encoded_salt, encoded_hash = stored_hash.split(
            "$", 3
        )
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        iterations = int(iterations_str)
    except ValueError:
        return False

    try:
        salt = base64.b64decode(encoded_salt)
        expected_hash = base64.b64decode(encoded_hash)
    except (binascii.Error, ValueError):
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )

    if len(derived) != len(expected_hash):
        return False

    return hmac.compare_digest(derived, expected_hash)


__all__ = [
    "SALT_BYTES",
    "PBKDF2_ITERATIONS",
    "JWT_ALGORITHM",
    "JWT_EXPIRATION_HOURS",
    "create_jwt_token",
    "get_session",
    "require_session",
    "hash_password",
    "verify_password",
]
