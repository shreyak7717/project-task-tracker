"""Login, refresh, /me, and the DB-authoritative authorization rules."""

from __future__ import annotations

from app.enums import Role
from app.security import create_access_token


def _login(client, email: str, password: str = "password123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_success_returns_token_pair(client, member):
    resp = _login(client, "member@example.com")
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


def test_login_wrong_password_is_401(client, member):
    resp = _login(client, "member@example.com", "nope")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password"


def test_login_unknown_email_is_401_with_same_message(client):
    resp = _login(client, "ghost@example.com")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password"


def test_login_inactive_user_is_401(client, make_user):
    make_user(email="frozen@example.com", active=False)
    assert _login(client, "frozen@example.com").status_code == 401


def test_login_normalizes_email(client, member):
    resp = _login(client, "  MEMBER@Example.Com  ")
    assert resp.status_code == 200


def test_me_requires_a_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_the_current_user(client, member, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers(member))
    assert resp.status_code == 200
    assert resp.json()["email"] == "member@example.com"


def test_refresh_issues_a_usable_access_token(client, member):
    refresh_token = _login(client, "member@example.com").json()["refresh_token"]
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200


def test_access_token_is_rejected_at_refresh(client, member):
    access_token = _login(client, "member@example.com").json()["access_token"]
    resp = client.post("/api/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


def test_refresh_token_is_rejected_as_a_bearer_credential(client, member):
    refresh_token = _login(client, "member@example.com").json()["refresh_token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 401


def test_stale_role_claim_is_not_trusted(client, member):
    # A token that claims manager for a user who is only a member in the DB.
    forged = create_access_token(str(member.id), Role.MANAGER)
    resp = client.get("/api/users", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 403


def test_deactivated_user_token_stops_working(client, member, auth_headers, db):
    headers = auth_headers(member)
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    member.is_active = False
    db.flush()
    assert client.get("/api/auth/me", headers=headers).status_code == 401
