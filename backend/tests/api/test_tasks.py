"""Task endpoints: CRUD, access, dependency rules, status transitions."""

from __future__ import annotations


def _task(client, headers, project_id, **overrides):
    body = {"title": "T", "description": "", "priority": "medium"}
    body.update(overrides)
    return client.post(f"/api/projects/{project_id}/tasks", json=body, headers=headers)


def _move(client, headers, task_id, to_status):
    return client.post(
        f"/api/tasks/{task_id}/transition", json={"to_status": to_status}, headers=headers
    )


def test_member_creates_a_task_in_their_project(client, member, auth_headers, make_project):
    project = make_project(members=(member,))
    resp = _task(client, auth_headers(member), project.id, title="Build login")
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "backlog"
    assert body["allowed_transitions"] == ["in_progress"]


def test_cannot_create_a_task_in_an_invisible_project(client, member, auth_headers, make_project):
    project = make_project()  # member is not on it
    assert _task(client, auth_headers(member), project.id).status_code == 404


def test_a_task_can_be_created_with_dependencies(client, manager, auth_headers, make_project):
    project = make_project()
    a = _task(client, auth_headers(manager), project.id, title="A").json()
    b = _task(
        client, auth_headers(manager), project.id, title="B", depends_on_task_ids=[a["id"]]
    ).json()
    assert [d["id"] for d in b["dependencies"]] == [a["id"]]


def test_list_project_tasks(client, manager, auth_headers, make_project):
    project = make_project()
    _task(client, auth_headers(manager), project.id, title="one")
    _task(client, auth_headers(manager), project.id, title="two")
    resp = client.get(f"/api/projects/{project.id}/tasks", headers=auth_headers(manager))
    assert {t["title"] for t in resp.json()} == {"one", "two"}


def test_patch_updates_fields(client, manager, auth_headers, make_project):
    project = make_project()
    task = _task(client, auth_headers(manager), project.id).json()
    resp = client.patch(
        f"/api/tasks/{task['id']}",
        json={"title": "Renamed", "priority": "high"},
        headers=auth_headers(manager),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed"
    assert resp.json()["priority"] == "high"


def test_patch_can_clear_the_due_date(client, manager, auth_headers, make_project):
    project = make_project()
    task = _task(client, auth_headers(manager), project.id, due_date="2026-01-01").json()
    assert task["due_date"] == "2026-01-01"
    resp = client.patch(
        f"/api/tasks/{task['id']}", json={"due_date": None}, headers=auth_headers(manager)
    )
    assert resp.json()["due_date"] is None


def test_only_a_manager_can_delete_a_task(client, manager, member, auth_headers, make_project):
    project = make_project(members=(member,))
    task = _task(client, auth_headers(member), project.id).json()
    assert client.delete(f"/api/tasks/{task['id']}", headers=auth_headers(member)).status_code == 403
    assert client.delete(f"/api/tasks/{task['id']}", headers=auth_headers(manager)).status_code == 204


def test_a_legal_transition_moves_the_task(client, manager, auth_headers, make_project):
    project = make_project()
    task = _task(client, auth_headers(manager), project.id).json()
    resp = _move(client, auth_headers(manager), task["id"], "in_progress")
    assert resp.status_code == 200 and resp.json()["status"] == "in_progress"


def test_an_illegal_transition_is_rejected_with_a_message(client, manager, auth_headers, make_project):
    project = make_project()
    task = _task(client, auth_headers(manager), project.id).json()
    resp = _move(client, auth_headers(manager), task["id"], "done")
    assert resp.status_code == 400
    assert "Illegal transition" in resp.json()["detail"]


def test_a_task_cannot_finish_while_a_blocker_is_unfinished(client, manager, auth_headers, make_project):
    project = make_project()
    blocker = _task(client, auth_headers(manager), project.id, title="Blocker").json()
    blocked = _task(
        client, auth_headers(manager), project.id, title="Blocked",
        depends_on_task_ids=[blocker["id"]],
    ).json()

    _move(client, auth_headers(manager), blocked["id"], "in_progress")
    _move(client, auth_headers(manager), blocked["id"], "in_review")
    refused = _move(client, auth_headers(manager), blocked["id"], "done")
    assert refused.status_code == 400 and "Blocker" in refused.json()["detail"]

    for step in ("in_progress", "in_review", "done"):
        _move(client, auth_headers(manager), blocker["id"], step)
    ok = _move(client, auth_headers(manager), blocked["id"], "done")
    assert ok.status_code == 200 and ok.json()["status"] == "done"


def test_dependency_rules(client, manager, auth_headers, make_project):
    project = make_project()
    other = make_project(key="OTHR")
    a = _task(client, auth_headers(manager), project.id, title="A").json()
    b = _task(client, auth_headers(manager), project.id, title="B").json()
    x = _task(client, auth_headers(manager), other.id, title="X").json()

    def add(task_id, dep_id):
        return client.post(
            f"/api/tasks/{task_id}/dependencies",
            json={"depends_on_task_id": dep_id},
            headers=auth_headers(manager),
        )

    assert add(b["id"], b["id"]).status_code == 400  # self
    assert add(b["id"], x["id"]).status_code == 400  # cross-project
    assert add(b["id"], a["id"]).status_code == 201  # ok
    assert add(b["id"], a["id"]).status_code == 409  # duplicate
    assert add(a["id"], b["id"]).status_code == 400  # immediate reverse


def test_removing_a_dependency(client, manager, auth_headers, make_project):
    project = make_project()
    a = _task(client, auth_headers(manager), project.id, title="A").json()
    b = _task(
        client, auth_headers(manager), project.id, title="B", depends_on_task_ids=[a["id"]]
    ).json()
    resp = client.delete(
        f"/api/tasks/{b['id']}/dependencies/{a['id']}", headers=auth_headers(manager)
    )
    assert resp.status_code == 204
    detail = client.get(f"/api/tasks/{b['id']}", headers=auth_headers(manager)).json()
    assert detail["dependencies"] == []


def test_done_is_withheld_from_allowed_transitions_until_the_blocker_finishes(
    client, manager, auth_headers, make_project
):
    project = make_project()
    a = _task(client, auth_headers(manager), project.id, title="A").json()
    b = _task(
        client, auth_headers(manager), project.id, title="B", depends_on_task_ids=[a["id"]]
    ).json()
    _move(client, auth_headers(manager), b["id"], "in_progress")
    detail = client.get(f"/api/tasks/{b['id']}", headers=auth_headers(manager)).json()
    assert "done" not in detail["allowed_transitions"]
    assert detail["blocked_by_unfinished_dependency"] is True
