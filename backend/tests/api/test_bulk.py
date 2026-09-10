"""Bulk actions: per-task results, atomicity, reuse of the real rules."""

from __future__ import annotations


def _task(client, headers, project_id, **overrides):
    body = {"title": "T", "description": "", "priority": "medium"}
    body.update(overrides)
    return client.post(f"/api/projects/{project_id}/tasks", json=body, headers=headers).json()


def _bulk(client, headers, task_ids, change):
    return client.post(
        "/api/tasks/bulk", json={"task_ids": task_ids, "change": change}, headers=headers
    )


def _status(client, headers, task_id):
    return client.get(f"/api/tasks/{task_id}", headers=headers).json()["status"]


def test_bulk_transition_reports_each_task(client, manager, auth_headers, make_project):
    p = make_project()
    good = _task(client, auth_headers(manager), p.id, title="good")
    bad = _task(client, auth_headers(manager), p.id, title="bad")
    client.post(
        f"/api/tasks/{good['id']}/transition",
        json={"to_status": "in_progress"},
        headers=auth_headers(manager),
    )

    resp = _bulk(
        client,
        auth_headers(manager),
        [good["id"], bad["id"]],
        {"kind": "transition", "to_status": "in_review"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["succeeded"] == 1 and body["failed"] == 1

    by_id = {r["task_id"]: r for r in body["results"]}
    assert by_id[good["id"]]["ok"] is True
    assert by_id[bad["id"]]["ok"] is False
    assert "Illegal transition" in by_id[bad["id"]]["error"]

    assert _status(client, auth_headers(manager), good["id"]) == "in_review"
    assert _status(client, auth_headers(manager), bad["id"]) == "backlog"  # untouched


def test_bulk_set_assignees_success(client, manager, make_user, auth_headers, make_project):
    a = make_user(email="a@example.com")
    b = make_user(email="b@example.com")
    p = make_project(members=(a, b))
    t1 = _task(client, auth_headers(manager), p.id, title="t1")
    t2 = _task(client, auth_headers(manager), p.id, title="t2")

    resp = _bulk(
        client,
        auth_headers(manager),
        [t1["id"], t2["id"]],
        {"kind": "set_assignees", "user_ids": [str(a.id), str(b.id)]},
    )
    assert resp.json()["succeeded"] == 2
    detail = client.get(f"/api/tasks/{t1['id']}", headers=auth_headers(manager)).json()
    assert {x["id"] for x in detail["assignees"]} == {str(a.id), str(b.id)}


def test_bulk_set_assignees_with_a_non_member_fails_every_task_atomically(
    client, manager, member, make_user, auth_headers, make_project
):
    outsider = make_user(email="out@example.com")
    p = make_project(members=(member,))
    t1 = _task(client, auth_headers(manager), p.id, title="t1")
    t2 = _task(client, auth_headers(manager), p.id, title="t2")

    resp = _bulk(
        client,
        auth_headers(manager),
        [t1["id"], t2["id"]],
        {"kind": "set_assignees", "user_ids": [str(member.id), str(outsider.id)]},
    )
    body = resp.json()
    assert body["succeeded"] == 0 and body["failed"] == 2
    # the valid assignee wasn't applied to either task
    detail = client.get(f"/api/tasks/{t1['id']}", headers=auth_headers(manager)).json()
    assert detail["assignees"] == []


def test_bulk_set_due_date_can_set_and_clear(client, manager, auth_headers, make_project):
    p = make_project()
    t1 = _task(client, auth_headers(manager), p.id, title="t1", due_date="2026-01-01")
    t2 = _task(client, auth_headers(manager), p.id, title="t2")

    _bulk(
        client,
        auth_headers(manager),
        [t1["id"], t2["id"]],
        {"kind": "set_due_date", "due_date": "2026-06-15"},
    )
    assert (
        client.get(f"/api/tasks/{t1['id']}", headers=auth_headers(manager)).json()["due_date"]
        == "2026-06-15"
    )

    _bulk(client, auth_headers(manager), [t1["id"]], {"kind": "set_due_date", "due_date": None})
    assert (
        client.get(f"/api/tasks/{t1['id']}", headers=auth_headers(manager)).json()["due_date"]
        is None
    )


def test_bulk_reports_tasks_the_caller_cannot_see_rather_than_failing_the_request(
    client, manager, member, auth_headers, make_project
):
    mine = make_project(key="MINE", members=(member,))
    other = make_project(key="OTHR")
    visible = _task(client, auth_headers(manager), mine.id, title="v")
    hidden = _task(client, auth_headers(manager), other.id, title="h")

    resp = _bulk(
        client,
        auth_headers(member),
        [visible["id"], hidden["id"]],
        {"kind": "transition", "to_status": "in_progress"},
    )
    assert resp.status_code == 200
    by_id = {r["task_id"]: r for r in resp.json()["results"]}
    assert by_id[visible["id"]]["ok"] is True
    assert by_id[hidden["id"]]["ok"] is False


def test_bulk_dedupes_task_ids(client, manager, auth_headers, make_project):
    p = make_project()
    task = _task(client, auth_headers(manager), p.id)
    resp = _bulk(
        client,
        auth_headers(manager),
        [task["id"], task["id"], task["id"]],
        {"kind": "transition", "to_status": "in_progress"},
    )
    assert len(resp.json()["results"]) == 1
