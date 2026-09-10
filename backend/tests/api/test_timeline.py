"""The task timeline: what gets recorded, ordering, and immutability."""

from __future__ import annotations


def _task(client, headers, project_id, **overrides):
    body = {"title": "T", "description": "", "priority": "medium"}
    body.update(overrides)
    return client.post(
        f"/api/projects/{project_id}/tasks", json=body, headers=headers
    ).json()


def _timeline(client, headers, task_id):
    return client.get(f"/api/tasks/{task_id}/timeline", headers=headers).json()


def test_creation_is_the_first_entry_with_the_actor(client, manager, auth_headers, make_project):
    project = make_project()
    task = _task(client, auth_headers(manager), project.id)
    timeline = _timeline(client, auth_headers(manager), task["id"])
    assert timeline[0]["event_type"] == "created"
    assert timeline[0]["actor"]["id"] == str(manager.id)


def test_field_edits_record_old_and_new(client, manager, auth_headers, make_project):
    project = make_project()
    task = _task(client, auth_headers(manager), project.id, title="Old")
    client.patch(
        f"/api/tasks/{task['id']}", json={"title": "New"}, headers=auth_headers(manager)
    )
    changed = [e for e in _timeline(client, auth_headers(manager), task["id"]) if e["event_type"] == "field_changed"]
    assert changed[-1]["field"] == "title"
    assert changed[-1]["old_value"] == "Old"
    assert changed[-1]["new_value"] == "New"


def test_status_change_and_comment_land_in_chronological_order(client, manager, auth_headers, make_project):
    project = make_project()
    task = _task(client, auth_headers(manager), project.id)
    client.post(
        f"/api/tasks/{task['id']}/transition",
        json={"to_status": "in_progress"},
        headers=auth_headers(manager),
    )
    client.post(
        f"/api/tasks/{task['id']}/comments", json={"body": "on it"}, headers=auth_headers(manager)
    )
    types = [e["event_type"] for e in _timeline(client, auth_headers(manager), task["id"])]
    assert types == ["created", "status_changed", "commented"]


def test_dependency_add_and_remove_are_recorded(client, manager, auth_headers, make_project):
    project = make_project()
    a = _task(client, auth_headers(manager), project.id, title="A")
    b = _task(client, auth_headers(manager), project.id, title="B")
    client.post(
        f"/api/tasks/{b['id']}/dependencies",
        json={"depends_on_task_id": a["id"]},
        headers=auth_headers(manager),
    )
    client.delete(
        f"/api/tasks/{b['id']}/dependencies/{a['id']}", headers=auth_headers(manager)
    )
    types = [e["event_type"] for e in _timeline(client, auth_headers(manager), b["id"])]
    assert "dependency_added" in types
    assert "dependency_removed" in types


def test_there_is_no_route_to_edit_or_delete_a_timeline_entry(client, manager, auth_headers, make_project):
    project = make_project()
    task = _task(client, auth_headers(manager), project.id)
    event_id = _timeline(client, auth_headers(manager), task["id"])[0]["id"]
    patch = client.patch(
        f"/api/tasks/{task['id']}/timeline/{event_id}", json={}, headers=auth_headers(manager)
    )
    delete = client.delete(
        f"/api/tasks/{task['id']}/timeline/{event_id}", headers=auth_headers(manager)
    )
    assert patch.status_code in (404, 405)
    assert delete.status_code in (404, 405)


def test_a_member_can_read_the_timeline_of_a_task_in_their_project(
    client, manager, member, auth_headers, make_project
):
    project = make_project(members=(member,))
    task = _task(client, auth_headers(manager), project.id)
    assert client.get(
        f"/api/tasks/{task['id']}/timeline", headers=auth_headers(member)
    ).status_code == 200
