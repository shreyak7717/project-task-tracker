"""The cross-project list: search, filters, sort, pagination, visibility."""

from __future__ import annotations

from datetime import date, timedelta


def _task(client, headers, project_id, **overrides):
    body = {"title": "T", "description": "", "priority": "medium"}
    body.update(overrides)
    return client.post(f"/api/projects/{project_id}/tasks", json=body, headers=headers).json()


def _list(client, headers, **params):
    return client.get("/api/tasks", params=params, headers=headers).json()


def _move(client, headers, task_id, *statuses):
    for s in statuses:
        client.post(f"/api/tasks/{task_id}/transition", json={"to_status": s}, headers=headers)


def test_search_covers_title_and_description(client, manager, auth_headers, make_project):
    p = make_project()
    _task(client, auth_headers(manager), p.id, title="Fix login bug")
    _task(client, auth_headers(manager), p.id, title="Other", description="the login flow")
    _task(client, auth_headers(manager), p.id, title="Unrelated")
    page = _list(client, auth_headers(manager), q="login")
    assert page["total"] == 2
    assert {i["title"] for i in page["items"]} == {"Fix login bug", "Other"}


def test_search_escapes_like_wildcards(client, manager, auth_headers, make_project):
    p = make_project()
    _task(client, auth_headers(manager), p.id, title="100% done")
    _task(client, auth_headers(manager), p.id, title="nothing here")
    assert {i["title"] for i in _list(client, auth_headers(manager), q="100%")["items"]} == {
        "100% done"
    }


def test_filter_by_status_and_priority(client, manager, auth_headers, make_project):
    p = make_project()
    a = _task(client, auth_headers(manager), p.id, title="a", priority="high")
    _task(client, auth_headers(manager), p.id, title="b", priority="low")
    _move(client, auth_headers(manager), a["id"], "in_progress")
    assert {
        i["title"] for i in _list(client, auth_headers(manager), status="in_progress")["items"]
    } == {"a"}
    assert {i["title"] for i in _list(client, auth_headers(manager), priority="high")["items"]} == {
        "a"
    }


def test_filter_by_assignee_and_unassigned(client, manager, member, auth_headers, make_project):
    p = make_project(members=(member,))
    assigned = _task(client, auth_headers(manager), p.id, title="assigned")
    _task(client, auth_headers(manager), p.id, title="free")
    client.post(f"/api/tasks/{assigned['id']}/assignees/{member.id}", headers=auth_headers(manager))
    assert {
        i["title"]
        for i in _list(client, auth_headers(manager), assignee_id=str(member.id))["items"]
    } == {"assigned"}
    assert {i["title"] for i in _list(client, auth_headers(manager), unassigned=True)["items"]} == {
        "free"
    }


def test_filter_overdue_excludes_future_and_done(client, manager, auth_headers, make_project):
    p = make_project()
    past = (date.today() - timedelta(days=3)).isoformat()
    future = (date.today() + timedelta(days=3)).isoformat()
    _task(client, auth_headers(manager), p.id, title="late", due_date=past)
    _task(client, auth_headers(manager), p.id, title="soon", due_date=future)
    done_late = _task(client, auth_headers(manager), p.id, title="done late", due_date=past)
    _move(client, auth_headers(manager), done_late["id"], "in_progress", "in_review", "done")

    assert {i["title"] for i in _list(client, auth_headers(manager), overdue=True)["items"]} == {
        "late"
    }


def test_sort_by_due_date_puts_nulls_last(client, manager, auth_headers, make_project):
    p = make_project()
    _task(client, auth_headers(manager), p.id, title="no date")
    _task(client, auth_headers(manager), p.id, title="early", due_date="2026-01-01")
    _task(client, auth_headers(manager), p.id, title="late", due_date="2026-12-01")
    items = _list(client, auth_headers(manager), sort="due_date", order="asc")["items"]
    assert [i["title"] for i in items] == ["early", "late", "no date"]


def test_sort_by_priority(client, manager, auth_headers, make_project):
    p = make_project()
    for title, prio in [("lo", "low"), ("hi", "urgent"), ("mid", "medium")]:
        _task(client, auth_headers(manager), p.id, title=title, priority=prio)
    items = _list(client, auth_headers(manager), sort="priority", order="desc")["items"]
    assert [i["title"] for i in items] == ["hi", "mid", "lo"]


def test_pagination_reports_total_and_pages(client, manager, auth_headers, make_project):
    p = make_project()
    for n in range(5):
        _task(client, auth_headers(manager), p.id, title=f"t{n}")
    first = _list(client, auth_headers(manager), page=1, page_size=2)
    assert first["total"] == 5 and first["pages"] == 3 and len(first["items"]) == 2
    last = _list(client, auth_headers(manager), page=3, page_size=2)
    assert len(last["items"]) == 1


def test_list_is_scoped_to_visible_projects(client, manager, member, auth_headers, make_project):
    mine = make_project(key="MINE", members=(member,))
    other = make_project(key="OTHER")
    _task(client, auth_headers(manager), mine.id, title="visible")
    _task(client, auth_headers(manager), other.id, title="hidden")
    assert {i["title"] for i in _list(client, auth_headers(member))["items"]} == {"visible"}


def test_list_item_carries_project_and_assignees(
    client, manager, member, auth_headers, make_project
):
    p = make_project(key="ACM", members=(member,))
    task = _task(client, auth_headers(manager), p.id, title="x")
    client.post(f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager))
    item = _list(client, auth_headers(manager), q="x")["items"][0]
    assert item["project_key"] == "ACM"
    assert [a["id"] for a in item["assignees"]] == [str(member.id)]
