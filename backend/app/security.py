"""Cryptographic helpers: password hashing, JWTs, and invitation tokens.

Pure functions — no FastAPI, no database. Everything here is unit-testable in
isolation (see tests/test_security.py).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

# bcrypt only hashes the first 72 bytes of a password. Rather than silently
# truncate, the API schemas cap password inputs at 72 characters and we treat
# anything longer as a client error there.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


# --- passwords -------------------------------------------------------------


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# Verified against when a login email is unknown, so an attacker can't tell
# "no such user" from "wrong password" by timing the response.
DUMMY_PASSWORD_HASH = pwd_context.hash("timing-equaliser-not-a-real-password")


# --- JSON Web Tokens ------------------------------------------------------


def _encode(claims: dict[str, Any], expires: timedelta, token_type: str) -> str:
    now = datetime.now(UTC)
    payload = {
        **claims,
        "iat": now,
        "exp": now + expires,
        "type": token_type,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, role: str) -> str:
    """Short-lived token. Carries ``role`` for convenience only — callers must
    still treat the database row as the source of truth for authorization."""
    return _encode(
        {"sub": str(subject), "role": role},
        timedelta(minutes=settings.access_token_expire_minutes),
        ACCESS_TOKEN_TYPE,
    )


def create_refresh_token(subject: str) -> str:
    """Long-lived token, exchanged at /api/auth/refresh for a new access token."""
    return _encode(
        {"sub": str(subject)},
        timedelta(days=settings.refresh_token_expire_days),
        REFRESH_TOKEN_TYPE,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Return the token's claims, or raise ``jose.JWTError`` if it is malformed,
    tampered with, or expired."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# --- invitation tokens ---------------------------------------------------


def generate_invite_token() -> tuple[str, str]:
    """Return ``(raw, token_hash)``.

    The raw token goes to the invitee exactly once (in the accept URL). Only the
    hash is stored, so a database leak does not hand out working invitations.
    """
    raw = secrets.token_urlsafe(32)
    return raw, hash_invite_token(raw)


def hash_invite_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
