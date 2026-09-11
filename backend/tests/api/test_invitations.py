"""The manager-issues / invitee-accepts account flow."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import select

from app.models import Invitation
from app.security import hash_invite_token
from app.services import email as email_service

ACCEPT = "/api/auth/invitations/accept"
INVITATIONS = "/api/users/invitations"


def _token_from_url(url: str) -> str:
    return parse_qs(urlparse(url).query)["token"][0]


def _invite(client, manager, auth_headers, email="newhire@example.com"):
    return client.post(INVITATIONS, json={"email": email}, headers=auth_headers(manager))


# --- creating ------------------------------------------------------------


def test_manager_creates_invitation_and_only_the_hash_is_stored(
    client, manager, auth_headers, db, monkeypatch
):
    # Force the "no provider configured" case explicitly rather than assuming
    # it — a real SENDGRID_API_KEY in the developer's local .env would
    # otherwise leak into this test and make it flaky depending on machine.
    monkeypatch.setattr(email_service.settings, "sendgrid_api_key", None)

    resp = _invite(client, manager, auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "newhire@example.com"
    assert body["role"] == "member"
    assert body["accepted_at"] is None
    # accept_url remains the fallback delivery path when nothing is sent.
    assert body["email_sent"] is False

    raw = _token_from_url(body["accept_url"])
    inv = db.scalar(select(Invitation).where(Invitation.email == "newhire@example.com"))
    assert inv.token_hash == hash_invite_token(raw)
    assert raw not in (inv.token_hash,)


def test_invitation_email_is_sent_when_a_provider_key_is_configured(
    client, manager, auth_headers, monkeypatch
):
    monkeypatch.setattr(email_service.settings, "sendgrid_api_key", "fake-key")
    monkeypatch.setattr(email_service.httpx, "post", lambda *a, **k: httpx.Response(202))

    resp = _invite(client, manager, auth_headers, email="emailed@example.com")
    assert resp.status_code == 201
    assert resp.json()["email_sent"] is True
    # accept_url is still returned even when the email send succeeded.
    assert "token=" in resp.json()["accept_url"]


def test_a_failed_send_does_not_affect_invitation_creation_or_acceptance(
    client, manager, auth_headers, monkeypatch
):
    """Email is best-effort: creating the invitation already committed before
    any send is attempted, so a broken provider must not change invitation
    state — still created, still single-use, still expires normally."""
    monkeypatch.setattr(email_service.settings, "sendgrid_api_key", "fake-key")

    def _raise(*a, **k):
        raise httpx.ConnectError("simulated provider outage")

    monkeypatch.setattr(email_service.httpx, "post", _raise)

    resp = _invite(client, manager, auth_headers, email="stillworks@example.com")
    assert resp.status_code == 201
    assert resp.json()["email_sent"] is False

    raw = _token_from_url(resp.json()["accept_url"])
    first = client.post(ACCEPT, json={"token": raw, "full_name": "A", "password": "password123"})
    assert first.status_code == 201
    second = client.post(ACCEPT, json={"token": raw, "full_name": "B", "password": "password123"})
    assert second.status_code == 400  # still single-use


def test_member_cannot_create_invitation(client, member, auth_headers):
    resp = client.post(INVITATIONS, json={"email": "x@example.com"}, headers=auth_headers(member))
    assert resp.status_code == 403


def test_unauthenticated_cannot_create_invitation(client):
    assert client.post(INVITATIONS, json={"email": "x@example.com"}).status_code == 401


def test_invitation_for_an_existing_user_email_conflicts(client, manager, member, auth_headers):
    assert _invite(client, manager, auth_headers, email=member.email).status_code == 409


# --- accepting ----------------------------------------------------------


def test_accept_creates_a_member_account_and_logs_them_in(client, manager, auth_headers, db):
    raw = _token_from_url(_invite(client, manager, auth_headers).json()["accept_url"])
    resp = client.post(
        ACCEPT, json={"token": raw, "full_name": "New Hire", "password": "s3cret-pw"}
    )
    assert resp.status_code == 201
    access = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == "newhire@example.com"
    assert me.json()["role"] == "member"

    inv = db.scalar(select(Invitation).where(Invitation.email == "newhire@example.com"))
    assert inv.accepted_at is not None
    assert inv.accepted_user_id is not None


def test_accept_unknown_token_is_400(client):
    resp = client.post(
        ACCEPT, json={"token": "not-real", "full_name": "X", "password": "password123"}
    )
    assert resp.status_code == 400


def test_accept_expired_token_is_400(client, make_invitation):
    _, raw = make_invitation(expires_in_days=-1)
    resp = client.post(ACCEPT, json={"token": raw, "full_name": "X", "password": "password123"})
    assert resp.status_code == 400


def test_accept_already_used_token_is_400(client, make_invitation):
    _, raw = make_invitation(accepted=True)
    resp = client.post(ACCEPT, json={"token": raw, "full_name": "X", "password": "password123"})
    assert resp.status_code == 400


def test_accepting_twice_fails_the_second_time(client, manager, auth_headers):
    raw = _token_from_url(_invite(client, manager, auth_headers).json()["accept_url"])
    first = client.post(ACCEPT, json={"token": raw, "full_name": "A", "password": "password123"})
    assert first.status_code == 201
    second = client.post(ACCEPT, json={"token": raw, "full_name": "B", "password": "password123"})
    assert second.status_code == 400


def test_a_new_invitation_supersedes_the_pending_one(client, manager, auth_headers):
    first = _token_from_url(_invite(client, manager, auth_headers).json()["accept_url"])
    second = _token_from_url(_invite(client, manager, auth_headers).json()["accept_url"])

    assert (
        client.post(
            ACCEPT, json={"token": first, "full_name": "A", "password": "password123"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            ACCEPT, json={"token": second, "full_name": "B", "password": "password123"}
        ).status_code
        == 201
    )


def test_accept_when_email_got_registered_meanwhile_is_409(
    client, manager, auth_headers, make_user, db
):
    raw = _token_from_url(
        _invite(client, manager, auth_headers, email="dup@example.com").json()["accept_url"]
    )
    make_user(email="dup@example.com")
    db.flush()
    resp = client.post(ACCEPT, json={"token": raw, "full_name": "Dup", "password": "password123"})
    assert resp.status_code == 409


def test_accept_rejects_a_short_password(client, make_invitation):
    _, raw = make_invitation()
    resp = client.post(ACCEPT, json={"token": raw, "full_name": "X", "password": "short"})
    assert resp.status_code == 422


# --- listing ------------------------------------------------------------


def test_list_invitations_is_manager_only(client, manager, member, auth_headers, make_invitation):
    make_invitation(email="pending@example.com")
    assert client.get(INVITATIONS, headers=auth_headers(member)).status_code == 403
    resp = client.get(INVITATIONS, headers=auth_headers(manager))
    assert resp.status_code == 200
    assert any(i["email"] == "pending@example.com" for i in resp.json())


def test_list_users_is_manager_only(client, manager, member, auth_headers):
    assert client.get("/api/users", headers=auth_headers(member)).status_code == 403
    resp = client.get("/api/users", headers=auth_headers(manager))
    assert resp.status_code == 200
    assert {u["email"] for u in resp.json()} >= {"manager@example.com", "member@example.com"}
