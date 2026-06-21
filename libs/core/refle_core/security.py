"""Password hashing (argon2) and JWT access tokens for the built-in auth provider."""

from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from refle_core.config import get_settings

_hasher = PasswordHasher()
_ALGORITHM = "HS256"
DEFAULT_TOKEN_TTL_MINUTES = 60 * 24  # 1 day


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except Argon2Error:
        return False


def create_access_token(
    subject: str,
    *,
    expires_minutes: int = DEFAULT_TOKEN_TTL_MINUTES,
    extra: dict[str, Any] | None = None,
) -> str:
    now = dt.datetime.now(dt.UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + dt.timedelta(minutes=expires_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_settings().secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a token. Raises ``jwt.PyJWTError`` on any problem."""
    return jwt.decode(token, get_settings().secret_key, algorithms=[_ALGORITHM])
