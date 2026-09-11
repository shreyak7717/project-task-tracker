"""Outbound transactional email via SendGrid's HTTP API (v3 Mail Send).

The first (and so far only) outbound network call in this backend. Kept
deliberately simple: one function, a one-shot request, no retry.

Best-effort by design: a failed or unconfigured send never raises and never
blocks whatever triggered it. When ``SENDGRID_API_KEY`` isn't set (the
default in local dev and in tests), no network call happens at all — the
caller falls back to whatever it already does without email (for
invitations, that's the ``accept_url`` returned in the API response).
"""

from __future__ import annotations

from datetime import datetime

import httpx

from app.config import settings

_SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


def send_invitation_email(*, to_email: str, accept_url: str, expires_at: datetime) -> bool:
    """Email an invitation accept link. Returns whether it was actually sent.

    Never raises: a missing API key, a non-2xx response (SendGrid returns 202
    on success, not 200), or a network error all just return False. The
    invitation itself is already committed to the database before this is
    ever called, so nothing about the invitation's state depends on the
    outcome here.
    """
    if not settings.sendgrid_api_key:
        return False

    html = f"""
    <p>You've been invited to join Task Tracker.</p>
    <p><a href="{accept_url}">Accept your invitation</a></p>
    <p>This link expires on {expires_at:%B %d, %Y} and can only be used once.</p>
    <p>If the link above doesn't work, copy and paste this URL:<br>{accept_url}</p>
    """

    try:
        resp = httpx.post(
            _SENDGRID_URL,
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": settings.email_from_address, "name": "Task Tracker"},
                "subject": "You've been invited to Task Tracker",
                "content": [{"type": "text/html", "value": html}],
            },
            timeout=5.0,
        )
        return resp.status_code < 300
    except httpx.RequestError:
        return False
