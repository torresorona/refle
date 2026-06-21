"""Symmetric encryption for secrets at rest (e.g. integration credentials).

Uses Fernet with a key derived from ``REFLE_SECRET_KEY``. For production/SaaS this
should move to envelope encryption with a cloud KMS; the interface stays the same.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet

from refle_core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
