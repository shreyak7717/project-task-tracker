"""CSV export: attachment headers, columns, and that it honours the filters."""

from __future__ import annotations

import csv
import io


def _task(client, headers, project_id, **overrides):
    body = {"title": "T", "description": "", "priority": "medium"}
    body.update(overrides)
    return client.post(f"/api/projects/{project_id}/tasks", json=body, headers=headers).json()


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_export_is_served_as_a_download(client, manager, auth_headers, make_project):
    make_project()
    resp = client.get("/api/tasks/export", headers=auth_headers(manager))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    disposition = resp.headers["content-disposition"]
    assert "attachment" in disposition and ".csv" in disposition


def test_export_columns_and_row_content(client, manager, member, auth_headers, make_project):
    project = make_project(key="ACM", members=(member,))
    task = _task(client, auth_headers(manager), project.id, title="Write docs", priority="high")
    client.post(f"/api/tasks/{task['id']}/assignees/{member.id}", headers=auth_headers(manager))

    rows = _rows(client.get("/api/tasks/export", headers=auth_headers(manager)).text)
    assert len(rows) == 1
    row = rows[0]
    assert row["project_key"] == "ACM"
    assert row["title"] == "Write docs"
    assert row["priority"] == "high"
    assert row["status"] == "backlog"
    assert row["assignees"] == "Mo Member"


def test_export_honours_the_active_filter(client, manager, auth_headers, make_project):
    project = make_project()
    _task(client, auth_headers(manager), project.id, title="keep me")
    _task(client, auth_headers(manager), project.id, title="drop me")
    rows = _rows(
        client.get("/api/tasks/export", params={"q": "keep"}, headers=auth_headers(manager)).text
    )
    assert [r["title"] for r in rows] == ["keep me"]


def test_export_is_scoped_to_visible_projects(client, manager, member, auth_headers, make_project):
    mine = make_project(key="MINE", members=(member,))
    make_project(key="OTHER")
    _task(client, auth_headers(manager), mine.id, title="visible")
    rows = _rows(client.get("/api/tasks/export", headers=auth_headers(member)).text)
    assert {r["title"] for r in rows} == {"visible"}
