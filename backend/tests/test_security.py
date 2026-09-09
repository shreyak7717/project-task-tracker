"""Unit tests for app.security — no database, no app."""

import time

import pytest
from jose import JWTError

from app import security


def test_password_hash_round_trip():
    hashed = security.hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert security.verify_password("correct horse battery staple", hashed)
    assert not security.verify_password("wrong password", hashed)


def test_access_token_carries_claims():
    token = security.create_access_token("user-123", "manager")
    claims = security.decode_token(token)
    assert claims["sub"] == "user-123"
    assert claims["role"] == "manager"
    assert claims["type"] == security.ACCESS_TOKEN_TYPE


def test_refresh_token_type():
    claims = security.decode_token(security.create_refresh_token("user-123"))
    assert claims["type"] == security.REFRESH_TOKEN_TYPE
    assert "role" not in claims


def test_tampered_token_rejected():
    token = security.create_access_token("user-123", "member")
    with pytest.raises(JWTError):
        security.decode_token(token + "x")


def test_expired_token_rejected(monkeypatch):
    monkeypatch.setattr(security.settings, "access_token_expire_minutes", -1)
    token = security.create_access_token("user-123", "member")
    with pytest.raises(JWTError):
        security.decode_token(token)


def test_invite_token_hash_is_stable_and_opaque():
    raw, token_hash = security.generate_invite_token()
    assert token_hash != raw
    assert len(token_hash) == 64
    assert security.hash_invite_token(raw) == token_hash


def test_invite_tokens_are_unique():
    assert security.generate_invite_token()[0] != security.generate_invite_token()[0]


def test_bcrypt_verify_speed_is_reasonable():
    # Guards against accidentally configuring an absurd cost factor.
    start = time.perf_counter()
    security.verify_password("x", security.hash_password("x"))
    assert time.perf_counter() - start < 2.0
