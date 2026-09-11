"""Dashboard aggregates (brief goal 8).

Everything is scoped to the caller's visible projects via the shared
``task_visibility_clause``, and archived projects' tasks are always excluded
(no toggle — a frozen project shouldn't skew a "what's going on" snapshot).
Every date boundary is derived from **one** UTC
reference computed here and passed as a bind parameter — the database session
timezone is never assumed to be UTC, so ``CURRENT_DATE`` / ``now()`` /
``date_trunc`` are not used.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import TaskStatus
from app.models import Project, Task, TaskAssignee, User
from app.services.visibility import task_visibility_clause

_OPEN = Task.status != TaskStatus.DONE.value
_ALL_STATUSES = [s.value for s in TaskStatus]
_WEEKS = 8


def _week_windows(today: date) -> list[tuple[date, date]]:
    """``_WEEKS`` rolling 7-day windows, oldest first. Newest = [today-6, today].

    Explicit boundaries, not date_trunc('week') — the definition is rolling
    7-day periods anchored to today, not Monday-based calendar weeks.
    """
    windows = []
    for i in range(_WEEKS - 1, -1, -1):
        end = today - timedelta(days=7 * i)
        windows.append((end - timedelta(days=6), end))
    return windows


def _utc_midnight(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=UTC)


def get_dashboard(
    db: Session, *, viewer: User, today: date | None = None, mine_only: bool = False
) -> dict:
    today = today or datetime.now(UTC).date()
    week_start = today - timedelta(days=6)
    windows = _week_windows(today)

    visible = task_visibility_clause(db, viewer)
    # Opt-in on top of visibility, not a replacement for it: "My work" still
    # only ever shows tasks in projects the caller can see, further narrowed
    # to ones they're personally assigned to.
    mine = (
        Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == viewer.id))
        if mine_only
        else None
    )

    def scoped(stmt):
        # Frozen work shouldn't skew a "what's going on" snapshot — unlike the
        # task lists, there's no "show archived" toggle here, so this is
        # unconditional rather than opt-in.
        stmt = stmt.where(
            Task.project_id.in_(select(Project.id).where(Project.is_archived.is_(False)))
        )
        if visible is not None:
            stmt = stmt.where(visible)
        if mine is not None:
            stmt = stmt.where(mine)
        return stmt

    headline = db.execute(
        scoped(
            select(
                func.count().filter(_OPEN).label("open"),
                func.count().filter(_OPEN, Task.due_date < today).label("overdue"),
                func.count()
                .filter(_OPEN, Task.due_date >= today, Task.due_date <= today + timedelta(days=6))
                .label("due_this_week"),
                func.count()
                .filter(Task.completed_at >= _utc_midnight(week_start))
                .label("completed_this_week"),
            ).select_from(Task)
        )
    ).one()

    status_counts = dict(
        db.execute(
            scoped(select(Task.status, func.count()).select_from(Task).group_by(Task.status))
        ).all()
    )
    by_status = [{"status": s, "count": status_counts.get(s, 0)} for s in _ALL_STATUSES]

    # M:N: an open task assigned to N people contributes 1 to each; the NULL
    # user_id row (outer join) is the unassigned bucket.
    assignee_rows = db.execute(
        scoped(
            select(TaskAssignee.user_id, func.count())
            .select_from(Task)
            .outerjoin(TaskAssignee, TaskAssignee.task_id == Task.id)
            .where(_OPEN)
            .group_by(TaskAssignee.user_id)
        )
    ).all()
    ids = [uid for uid, _ in assignee_rows if uid is not None]
    users = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    )
    by_assignee = sorted(
        ({"user": users.get(uid), "count": count} for uid, count in assignee_rows),
        key=lambda r: (-r["count"], r["user"].full_name if r["user"] else ""),
    )

    completed_ats = db.scalars(
        scoped(
            select(Task.completed_at)
            .select_from(Task)
            .where(
                Task.completed_at.is_not(None),
                Task.completed_at >= _utc_midnight(windows[0][0]),
            )
        )
    ).all()
    counts = [0] * _WEEKS
    for ts in completed_ats:
        d = ts.astimezone(UTC).date()
        for idx, (start, end) in enumerate(windows):
            if start <= d <= end:
                counts[idx] += 1
                break
    completions = [
        {"week_start": start.isoformat(), "count": counts[idx]}
        for idx, (start, _) in enumerate(windows)
    ]

    return {
        "headline": {
            "open": headline.open,
            "overdue": headline.overdue,
            "due_this_week": headline.due_this_week,
            "completed_this_week": headline.completed_this_week,
        },
        "by_status": by_status,
        "by_assignee": by_assignee,
        "completions_last_8_weeks": completions,
    }
