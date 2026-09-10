"""Task assignment: project-member rule, atomic replacement, cascade, timeline."""

from __future__ import annotations


def _task(client, headers, project_id, **overrides):
    body = {"title": "T", "description": "", "priority": "medium"}
    body.update(overrides)
    return client.post(f"/api/projects/{project_id}/tasks", json=body, headers=headers).json()


def _assignee_ids(detail: dict) -> set[str]:
    return {a["id"] for a in detail["assignees"]}


def test_assign_a_project_member(client, manager, member, auth_headers, make_project):
    project = make_project(members=(member,))
    task = _task(client, auth_headers(manager), project.id)
    resp = client.post(
        f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager)
    )
    assert resp.status_code == 201
    assert _assignee_ids(resp.json()) == {str(member.id)}


def test_cannot_assign_a_non_member(client, manager, member, make_user, auth_headers, make_project):
    project = make_project(members=(member,))
    outsider = make_user(email="out@example.com")
    task = _task(client, auth_headers(manager), project.id)
    resp = client.post(
        f"/api/tasks/{task['id']}/assignees/{outsider.id}", headers=auth_headers(manager)
    )
    assert resp.status_code == 400
    assert "not a member" in resp.json()["detail"]


def test_assign_is_idempotent(client, manager, member, auth_headers, make_project):
    project = make_project(members=(member,))
    task = _task(client, auth_headers(manager), project.id)
    for _ in range(2):
        client.post(f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager))
    detail = client.get(f"/api/tasks/{task['id']}", headers=auth_headers(manager)).json()
    assert len(detail["assignees"]) == 1


def test_unassign(client, manager, member, auth_headers, make_project):
    project = make_project(members=(member,))
    task = _task(client, auth_headers(manager), project.id)
    client.post(f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager))
    resp = client.delete(
        f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager)
    )
    assert resp.status_code == 204
    detail = client.get(f"/api/tasks/{task['id']}", headers=auth_headers(manager)).json()
    assert detail["assignees"] == []


def test_unassigning_someone_not_assigned_is_404(
    client, manager, member, auth_headers, make_project
):
    project = make_project(members=(member,))
    task = _task(client, auth_headers(manager), project.id)
    resp = client.delete(
        f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager)
    )
    assert resp.status_code == 404


def test_put_replaces_the_whole_assignee_set(
    client, manager, make_user, auth_headers, make_project
):
    a = make_user(email="a@example.com")
    b = make_user(email="b@example.com")
    project = make_project(members=(a, b))
    task = _task(client, auth_headers(manager), project.id)

    client.put(
        f"/api/tasks/{task['id']}/assignees",
        json={"user_ids": [str(a.id)]},
        headers=auth_headers(manager),
    )
    resp = client.put(
        f"/api/tasks/{task['id']}/assignees",
        json={"user_ids": [str(b.id)]},
        headers=auth_headers(manager),
    )
    assert _assignee_ids(resp.json()) == {str(b.id)}


def test_put_with_a_non_member_rejects_the_whole_change(
    client, manager, make_user, auth_headers, make_project
):
    a = make_user(email="a@example.com")
    outsider = make_user(email="out@example.com")
    project = make_project(members=(a,))
    task = _task(client, auth_headers(manager), project.id)
    client.put(
        f"/api/tasks/{task['id']}/assignees",
        json={"user_ids": [str(a.id)]},
        headers=auth_headers(manager),
    )

    resp = client.put(
        f"/api/tasks/{task['id']}/assignees",
        json={"user_ids": [str(a.id), str(outsider.id)]},
        headers=auth_headers(manager),
    )
    assert resp.status_code == 400
    detail = client.get(f"/api/tasks/{task['id']}", headers=auth_headers(manager)).json()
    assert _assignee_ids(detail) == {str(a.id)}  # nothing changed


def test_a_member_can_assign_within_their_project(
    client, manager, member, auth_headers, make_project
):
    project = make_project(members=(member,))
    task = _task(client, auth_headers(manager), project.id)
    resp = client.post(
        f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(member)
    )
    assert resp.status_code == 201


def test_a_non_member_cannot_touch_assignees(client, manager, member, auth_headers, make_project):
    project = make_project()  # member is not on it
    task = _task(client, auth_headers(manager), project.id)
    resp = client.put(
        f"/api/tasks/{task['id']}/assignees", json={"user_ids": []}, headers=auth_headers(member)
    )
    assert resp.status_code == 404


def test_a_manager_can_assign_without_being_a_member(
    client, manager, member, auth_headers, make_project
):
    project = make_project(key="MEM", owner=member)  # manager is not a member here
    task = _task(client, auth_headers(member), project.id)
    resp = client.post(
        f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager)
    )
    assert resp.status_code == 201


def test_assigned_to_me_spans_projects(client, manager, member, auth_headers, make_project):
    p1 = make_project(key="P1", members=(member,))
    p2 = make_project(key="P2", members=(member,))
    mine1 = _task(client, auth_headers(manager), p1.id, title="mine1")
    mine2 = _task(client, auth_headers(manager), p2.id, title="mine2")
    _task(client, auth_headers(manager), p1.id, title="not mine")
    for task in (mine1, mine2):
        client.post(f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager))

    resp = client.get("/api/me/tasks", headers=auth_headers(member))
    assert resp.status_code == 200
    assert {i["title"] for i in resp.json()["items"]} == {"mine1", "mine2"}


def test_removing_a_member_from_a_project_unassigns_their_tasks(
    client, manager, member, auth_headers, make_project
):
    project = make_project(members=(member,))
    task = _task(client, auth_headers(manager), project.id)
    client.post(f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager))
    client.delete(f"/api/projects/{project.id}/members/{member.id}", headers=auth_headers(manager))

    detail = client.get(f"/api/tasks/{task['id']}", headers=auth_headers(manager)).json()
    assert detail["assignees"] == []
    timeline = client.get(f"/api/tasks/{task['id']}/timeline", headers=auth_headers(manager)).json()
    unassigned = [e for e in timeline if e["event_type"] == "unassigned"]
    assert unassigned and unassigned[-1]["actor"] is None  # system event


def test_assignment_events_land_in_the_timeline(
    client, manager, member, auth_headers, make_project
):
    project = make_project(members=(member,))
    task = _task(client, auth_headers(manager), project.id)
    client.post(f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager))
    client.delete(f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager))
    types = [
        e["event_type"]
        for e in client.get(
            f"/api/tasks/{task['id']}/timeline", headers=auth_headers(manager)
        ).json()
    ]
    assert types == ["created", "assigned", "unassigned"]
