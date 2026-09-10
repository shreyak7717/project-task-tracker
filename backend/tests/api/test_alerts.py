"""Overdue alerts: detection, scoping, dismissal rules, resurfacing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.enums import TaskStatus as S
from app.models import AlertDismissal, TaskAssignee


def _alerts(client, headers) -> dict:
    return client.get("/api/alerts", headers=headers).json()


def _due(days_from_today: int):
    return datetime.now(UTC).date() + timedelta(days=days_from_today)


def _assign(db, task, user) -> None:
    db.add(TaskAssignee(task_id=task.id, user_id=user.id))
    db.flush()


def test_overdue_unfinished_tasks_appear_as_alerts(
    client, manager, auth_headers, make_project, make_task, db
):
    p = make_project()
    make_task(project=p, status=S.IN_PROGRESS, due_date=_due(-2), title="late")
    make_task(project=p, status=S.IN_PROGRESS, due_date=_due(2), title="soon")
    make_task(
        project=p,
        status=S.DONE,
        due_date=_due(-5),
        title="done late",
        completed_at=datetime.now(UTC),
    )
    make_task(project=p, status=S.BACKLOG, title="no due date")
    db.flush()

    body = _alerts(client, auth_headers(manager))
    assert [i["title"] for i in body["items"]] == ["late"]
    assert body["count"] == 1
    assert body["items"][0]["days_overdue"] == 2


def test_alerts_are_scoped_to_visible_projects(
    client, manager, member, auth_headers, make_project, make_task, db
):
    mine = make_project(key="MINE", members=(member,))
    other = make_project(key="OTHER")
    make_task(project=mine, status=S.BACKLOG, due_date=_due(-1), title="mine")
    make_task(project=other, status=S.BACKLOG, due_date=_due(-1), title="other")
    db.flush()

    assert {i["title"] for i in _alerts(client, auth_headers(member))["items"]} == {"mine"}
    assert {i["title"] for i in _alerts(client, auth_headers(manager))["items"]} == {
        "mine",
        "other",
    }


def test_dismiss_requires_being_assigned(
    client, manager, member, auth_headers, make_project, make_task, db
):
    p = make_project(members=(member,))
    task = make_task(project=p, status=S.BACKLOG, due_date=_due(-1))
    db.flush()
    resp = client.post(f"/api/alerts/{task.id}/dismiss", headers=auth_headers(member))
    assert resp.status_code == 403


def test_dismiss_hides_the_alert_and_drops_the_count(
    client, member, auth_headers, make_project, make_task, db
):
    p = make_project(members=(member,))
    task = make_task(project=p, status=S.BACKLOG, due_date=_due(-1))
    _assign(db, task, member)

    assert _alerts(client, auth_headers(member))["count"] == 1
    resp = client.post(f"/api/alerts/{task.id}/dismiss", headers=auth_headers(member))
    assert resp.status_code == 204
    assert _alerts(client, auth_headers(member))["count"] == 0
    assert client.get("/api/alerts/count", headers=auth_headers(member)).json()["count"] == 0


def test_changing_the_due_date_resurfaces_a_dismissed_alert(
    client, manager, member, auth_headers, make_project, make_task, db
):
    p = make_project(members=(member,))
    task = make_task(project=p, status=S.BACKLOG, due_date=_due(-3))
    _assign(db, task, member)
    client.post(f"/api/alerts/{task.id}/dismiss", headers=auth_headers(member))
    assert _alerts(client, auth_headers(member))["count"] == 0

    client.patch(
        f"/api/tasks/{task.id}",
        json={"due_date": _due(-1).isoformat()},
        headers=auth_headers(manager),
    )
    assert _alerts(client, auth_headers(member))["count"] == 1


def test_redismissing_is_idempotent(client, member, auth_headers, make_project, make_task, db):
    p = make_project(members=(member,))
    task = make_task(project=p, status=S.BACKLOG, due_date=_due(-2))
    _assign(db, task, member)

    for _ in range(3):
        assert (
            client.post(f"/api/alerts/{task.id}/dismiss", headers=auth_headers(member)).status_code
            == 204
        )

    rows = db.scalars(select(AlertDismissal).where(AlertDismissal.task_id == task.id)).all()
    assert len(rows) == 1
    assert rows[0].dismissed_due_date == _due(-2)


def test_dismiss_on_a_not_yet_overdue_task_is_400(
    client, member, auth_headers, make_project, make_task, db
):
    p = make_project(members=(member,))
    task = make_task(project=p, status=S.BACKLOG, due_date=_due(5))
    _assign(db, task, member)
    resp = client.post(f"/api/alerts/{task.id}/dismiss", headers=auth_headers(member))
    assert resp.status_code == 400


def test_dismiss_on_an_invisible_task_is_404(
    client, member, auth_headers, make_project, make_task, db
):
    p = make_project()  # member is not on it
    task = make_task(project=p, status=S.BACKLOG, due_date=_due(-1))
    db.flush()
    resp = client.post(f"/api/alerts/{task.id}/dismiss", headers=auth_headers(member))
    assert resp.status_code == 404
