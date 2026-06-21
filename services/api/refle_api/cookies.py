"""Session cookie helpers.

The JWT is delivered to browsers as an httpOnly cookie (not readable by JS, so
less exposed to XSS). API clients may still use the Bearer token from the response
body. Cookie is Secure in production; SameSite=Lax works for same-site app/api hosts.
"""

from __future__ import annotations

from fastapi import Response
from refle_core.config import get_settings
from refle_core.security import DEFAULT_TOKEN_TTL_MINUTES

COOKIE_NAME = "refle_session"


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=get_settings().is_production,
        samesite="lax",
        max_age=DEFAULT_TOKEN_TTL_MINUTES * 60,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
