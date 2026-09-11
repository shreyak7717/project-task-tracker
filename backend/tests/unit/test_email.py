"""Unit tests for app.services.email — no database, no app. httpx is mocked;
nothing here makes a real network call.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.services import email


def _expires() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def test_no_api_key_configured_skips_send_and_returns_false(monkeypatch):
    monkeypatch.setattr(email.settings, "sendgrid_api_key", None)
    called = False

    def _fake_post(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(email.httpx, "post", _fake_post)

    sent = email.send_invitation_email(
        to_email="dev@example.com", accept_url="https://x/accept-invite?token=t", expires_at=_expires()
    )
    assert sent is False
    assert called is False


def test_successful_send_returns_true_with_the_right_shape(monkeypatch):
    monkeypatch.setattr(email.settings, "sendgrid_api_key", "fake-key")
    monkeypatch.setattr(email.settings, "email_from_address", "invites@example.com")
    captured = {}

    def _fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return httpx.Response(202)  # SendGrid's real success code, not 200

    monkeypatch.setattr(email.httpx, "post", _fake_post)

    sent = email.send_invitation_email(
        to_email="dev@example.com",
        accept_url="https://x/accept-invite?token=t",
        expires_at=_expires(),
    )
    assert sent is True
    assert captured["url"] == "https://api.sendgrid.com/v3/mail/send"
    assert captured["headers"]["Authorization"] == "Bearer fake-key"
    assert captured["json"]["personalizations"] == [{"to": [{"email": "dev@example.com"}]}]
    assert captured["json"]["from"] == {"email": "invites@example.com", "name": "Task Tracker"}
    assert "https://x/accept-invite?token=t" in captured["json"]["content"][0]["value"]


def test_non_2xx_response_returns_false(monkeypatch):
    monkeypatch.setattr(email.settings, "sendgrid_api_key", "fake-key")
    monkeypatch.setattr(email.httpx, "post", lambda *a, **k: httpx.Response(403, json={}))

    sent = email.send_invitation_email(
        to_email="dev@example.com", accept_url="https://x/accept-invite?token=t", expires_at=_expires()
    )
    assert sent is False


def test_network_error_returns_false_not_an_exception(monkeypatch):
    monkeypatch.setattr(email.settings, "sendgrid_api_key", "fake-key")

    def _raise(*a, **k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(email.httpx, "post", _raise)

    sent = email.send_invitation_email(
        to_email="dev@example.com", accept_url="https://x/accept-invite?token=t", expires_at=_expires()
    )
    assert sent is False
