"""Project and membership endpoints: manager gates, visibility, archiving."""

from __future__ import annotations

import uuid


def _create(client, actor, auth_headers, *, key="ACME", name="Acme", owner=None):
    body = {
        "key": key,
        "name": name,
        "description": "",
        "owner_id": str((owner or actor).id),
    }
    return client.post("/api/projects", json=body, headers=auth_headers(actor))


# --- creation -----------------------------------------------------------


def test_manager_creates_project_and_owner_becomes_a_member(client, manager, member, auth_headers):
    resp = _create(client, manager, auth_headers, owner=member)
    assert resp.status_code == 201
    project = resp.json()
    assert project["key"] == "ACME"
    assert project["owner"]["id"] == str(member.id)

    members = client.get(
        f"/api/projects/{project['id']}/members", headers=auth_headers(manager)
    ).json()
    assert [m["user"]["id"] for m in members] == [str(member.id)]


def test_member_cannot_create_a_project(client, member, auth_headers):
    assert _create(client, member, auth_headers).status_code == 403


def test_duplicate_key_conflicts_case_insensitively(client, manager, auth_headers):
    assert _create(client, manager, auth_headers, key="DUP").status_code == 201
    assert _create(client, manager, auth_headers, key="dup", name="Other").status_code == 409


def test_malformed_key_is_422(client, manager, auth_headers):
    assert _create(client, manager, auth_headers, key="a").status_code == 422


def test_owner_must_be_a_real_user(client, manager, auth_headers):
    body = {"key": "ACME", "name": "x", "description": "", "owner_id": str(uuid.uuid4())}
    assert client.post("/api/projects", json=body, headers=auth_headers(manager)).status_code == 400


# --- visibility -------------------------------------------------------


def test_member_lists_only_their_projects(client, member, auth_headers, make_project):
    make_project(key="MINE", members=(member,))
    make_project(key="OTHER")
    resp = client.get("/api/projects", headers=auth_headers(member))
    assert resp.status_code == 200
    assert [p["key"] for p in resp.json()] == ["MINE"]


def test_manager_lists_all_projects(client, manager, auth_headers, make_project):
    make_project(key="AAA")
    make_project(key="BBB")
    keys = {p["key"] for p in client.get("/api/projects", headers=auth_headers(manager)).json()}
    assert {"AAA", "BBB"} <= keys


def test_member_gets_404_for_a_project_they_are_not_on(client, member, auth_headers, make_project):
    project = make_project(key="SECRET")
    assert (
        client.get(f"/api/projects/{project.id}", headers=auth_headers(member)).status_code == 404
    )


def test_member_can_get_a_project_they_are_on(client, member, auth_headers, make_project):
    project = make_project(key="OPEN", members=(member,))
    assert (
        client.get(f"/api/projects/{project.id}", headers=auth_headers(member)).status_code == 200
    )


# --- archiving -------------------------------------------------------


def test_archived_projects_are_hidden_from_the_default_list(
    client, manager, auth_headers, make_project
):
    make_project(key="LIVE")
    make_project(key="OLD", archived=True)

    default = {p["key"] for p in client.get("/api/projects", headers=auth_headers(manager)).json()}
    assert "LIVE" in default and "OLD" not in default

    with_archived = client.get(
        "/api/projects?include_archived=true", headers=auth_headers(manager)
    ).json()
    assert {"LIVE", "OLD"} <= {p["key"] for p in with_archived}


def test_archive_then_restore(client, manager, auth_headers, make_project):
    project = make_project(key="ARCH")
    archived = client.post(f"/api/projects/{project.id}/archive", headers=auth_headers(manager))
    assert archived.json()["is_archived"] is True
    restored = client.post(f"/api/projects/{project.id}/restore", headers=auth_headers(manager))
    assert restored.json()["is_archived"] is False


# --- updates + membership -------------------------------------------


def test_manager_updates_and_member_cannot(client, manager, member, auth_headers, make_project):
    project = make_project(key="ED", members=(member,))
    ok = client.patch(
        f"/api/projects/{project.id}", json={"name": "Renamed"}, headers=auth_headers(manager)
    )
    assert ok.status_code == 200 and ok.json()["name"] == "Renamed"

    denied = client.patch(
        f"/api/projects/{project.id}", json={"name": "Nope"}, headers=auth_headers(member)
    )
    assert denied.status_code == 403


def test_adding_a_member_grants_them_visibility_removing_revokes_it(
    client, manager, member, auth_headers, make_project
):
    project = make_project(key="TEAM")
    assert (
        client.get(f"/api/projects/{project.id}", headers=auth_headers(member)).status_code == 404
    )

    added = client.put(
        f"/api/projects/{project.id}/members/{member.id}", headers=auth_headers(manager)
    )
    assert added.status_code == 200
    assert (
        client.get(f"/api/projects/{project.id}", headers=auth_headers(member)).status_code == 200
    )

    removed = client.delete(
        f"/api/projects/{project.id}/members/{member.id}", headers=auth_headers(manager)
    )
    assert removed.status_code == 204
    assert (
        client.get(f"/api/projects/{project.id}", headers=auth_headers(member)).status_code == 404
    )


def test_the_owner_cannot_be_removed_from_their_project(
    client, manager, auth_headers, make_project
):
    project = make_project(key="OWN")  # owner defaults to the manager
    resp = client.delete(
        f"/api/projects/{project.id}/members/{manager.id}", headers=auth_headers(manager)
    )
    assert resp.status_code == 400


def test_a_member_cannot_manage_membership(
    client, manager, member, make_user, auth_headers, make_project
):
    project = make_project(key="TEAM", members=(member,))
    other = make_user(email="other@example.com")
    resp = client.put(
        f"/api/projects/{project.id}/members/{other.id}", headers=auth_headers(member)
    )
    assert resp.status_code == 403
