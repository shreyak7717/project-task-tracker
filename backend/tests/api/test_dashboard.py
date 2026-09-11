"""Dashboard aggregates: headline maths, breakdowns, rolling 8-week chart."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.enums import TaskStatus as S
from app.models import TaskAssignee


def _dashboard(client, headers, *, scope: str | None = None) -> dict:
    params = {"scope": scope} if scope else {}
    return client.get("/api/dashboard", headers=headers, params=params).json()


def _days_ago(n: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=n)


def _due_in(n: int):
    return datetime.now(UTC).date() + timedelta(days=n)


def test_headline_numbers(client, manager, auth_headers, make_project, make_task, db):
    p = make_project()
    make_task(project=p, status=S.BACKLOG)  # open
    make_task(project=p, status=S.IN_PROGRESS, due_date=_due_in(-2))  # open + overdue
    make_task(project=p, status=S.IN_REVIEW, due_date=_due_in(3))  # open + due this week
    make_task(project=p, status=S.DONE, completed_at=_days_ago(1))  # completed this week
    make_task(project=p, status=S.DONE, completed_at=_days_ago(40))  # completed long ago
    db.flush()

    headline = _dashboard(client, auth_headers(manager))["headline"]
    assert headline["open"] == 3
    assert headline["overdue"] == 1
    assert headline["due_this_week"] == 1
    assert headline["completed_this_week"] == 1


def test_by_status_is_zero_filled_for_all_statuses(
    client, manager, auth_headers, make_project, make_task, db
):
    p = make_project()
    make_task(project=p, status=S.BACKLOG)
    make_task(project=p, status=S.BACKLOG)
    db.flush()

    by_status = {
        r["status"]: r["count"] for r in _dashboard(client, auth_headers(manager))["by_status"]
    }
    assert by_status == {
        "backlog": 2,
        "in_progress": 0,
        "in_review": 0,
        "done": 0,
        "blocked": 0,
    }


def test_by_assignee_counts_each_assignee_and_the_unassigned_bucket(
    client, manager, make_user, auth_headers, make_project, make_task, db
):
    a = make_user(email="a@example.com")
    b = make_user(email="b@example.com")
    p = make_project(members=(a, b))
    shared = make_task(project=p, status=S.BACKLOG)
    solo = make_task(project=p, status=S.IN_PROGRESS)
    make_task(project=p, status=S.BACKLOG)  # unassigned
    db.flush()
    db.add_all(
        [
            TaskAssignee(task_id=shared.id, user_id=a.id),
            TaskAssignee(task_id=shared.id, user_id=b.id),
            TaskAssignee(task_id=solo.id, user_id=a.id),
        ]
    )
    db.flush()

    rows = _dashboard(client, auth_headers(manager))["by_assignee"]
    counts = {(r["user"]["email"] if r["user"] else None): r["count"] for r in rows}
    assert counts["a@example.com"] == 2  # shared + solo
    assert counts["b@example.com"] == 1  # shared
    assert counts[None] == 1  # the unassigned task


def test_eight_week_chart_buckets_completions(
    client, manager, auth_headers, make_project, make_task, db
):
    p = make_project()
    make_task(project=p, status=S.DONE, completed_at=_days_ago(1))  # newest bucket
    make_task(project=p, status=S.DONE, completed_at=_days_ago(10))  # ~2 buckets back
    make_task(project=p, status=S.DONE, completed_at=_days_ago(70))  # older than 8 weeks
    db.flush()

    chart = _dashboard(client, auth_headers(manager))["completions_last_8_weeks"]
    assert len(chart) == 8
    assert chart[-1]["count"] == 1  # completed this week
    assert sum(c["count"] for c in chart) == 2  # the 70-day-old one is excluded
    assert [c["week_start"] for c in chart] == sorted(c["week_start"] for c in chart)


def test_dashboard_is_scoped_to_visible_projects(
    client, manager, member, auth_headers, make_project, make_task, db
):
    mine = make_project(key="MINE", members=(member,))
    other = make_project(key="OTHER")
    make_task(project=mine, status=S.BACKLOG)
    make_task(project=other, status=S.BACKLOG)
    make_task(project=other, status=S.BACKLOG)
    db.flush()

    assert _dashboard(client, auth_headers(member))["headline"]["open"] == 1
    assert _dashboard(client, auth_headers(manager))["headline"]["open"] == 3


def test_default_scope_is_every_visible_task_unchanged(
    client, manager, auth_headers, make_project, make_task, db
):
    """Omitting `scope` (and passing `scope=team` explicitly) behaves exactly
    like today, before this param existed."""
    p = make_project()
    make_task(project=p, status=S.BACKLOG)
    make_task(project=p, status=S.IN_PROGRESS)
    db.flush()

    no_param = _dashboard(client, auth_headers(manager))
    explicit_team = _dashboard(client, auth_headers(manager), scope="team")
    assert no_param["headline"]["open"] == 2
    assert explicit_team == no_param


def test_scope_mine_restricts_to_the_callers_own_assigned_tasks(
    client, manager, member, auth_headers, make_project, make_task, db
):
    p = make_project(key="MINE", members=(member,))
    mine_task = make_task(project=p, status=S.BACKLOG, title="assigned to member")
    other_task = make_task(project=p, status=S.BACKLOG, title="assigned to someone else")
    make_task(project=p, status=S.BACKLOG, title="unassigned")
    db.flush()
    db.add_all(
        [
            TaskAssignee(task_id=mine_task.id, user_id=member.id),
            TaskAssignee(task_id=other_task.id, user_id=manager.id),
        ]
    )
    db.flush()

    team_view = _dashboard(client, auth_headers(member), scope="team")
    mine_view = _dashboard(client, auth_headers(member), scope="mine")

    # Team scope: every task in a project member belongs to, regardless of
    # who it's assigned to (unchanged, existing behavior).
    assert team_view["headline"]["open"] == 3
    # Mine scope: narrows further, within that same visible project, to just
    # the one task assigned to member.
    assert mine_view["headline"]["open"] == 1
    assert {r["status"]: r["count"] for r in mine_view["by_status"]}["backlog"] == 1
