"""Overdue alerts and their per-user dismissal (brief goal 10).

An alert is a task that is past its due date and not done, in one of the
caller's visible projects, that this caller has not dismissed *at the task's
current due date*. Because the dismissal stores the due date it was made
against, changing a task's due date makes the stored value stop matching and
the alert reappears.

All date comparisons use one UTC reference supplied by the caller (the router),
never the database session clock.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Select, exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.enums import TaskStatus
from app.models import AlertDismissal, Task, TaskAssignee, User
from app.services.errors import PermissionDeniedError, ValidationError
from app.services.tasks import get_visible_task_or_404
from app.services.visibility import task_visibility_clause


def _today(today: date | None) -> date:
    return today or datetime.now(UTC).date()


def _active_alerts(db: Session, viewer: User, today: date) -> Select:
    dismissed = exists().where(
        AlertDismissal.task_id == Task.id,
        AlertDismissal.user_id == viewer.id,
        AlertDismissal.dismissed_due_date == Task.due_date,
    )
    stmt = select(Task).where(
        Task.due_date.is_not(None),
        Task.due_date < today,
        Task.status != TaskStatus.DONE.value,
        ~dismissed,
    )
    visible = task_visibility_clause(db, viewer)
    if visible is not None:
        stmt = stmt.where(visible)
    return stmt


def list_alerts(db: Session, *, viewer: User, today: date | None = None) -> list[Task]:
    today = _today(today)
    stmt = (
        _active_alerts(db, viewer, today)
        .options(selectinload(Task.project))
        .order_by(Task.due_date, Task.id)
    )
    return list(db.scalars(stmt))


def alert_count(db: Session, *, viewer: User, today: date | None = None) -> int:
    today = _today(today)
    subquery = _active_alerts(db, viewer, today).subquery()
    return db.scalar(select(func.count()).select_from(subquery)) or 0


def dismiss(db: Session, *, viewer: User, task_id: uuid.UUID, today: date | None = None) -> None:
    today = _today(today)
    task = get_visible_task_or_404(db, user=viewer, task_id=task_id)

    overdue = (
        task.due_date is not None
        and task.due_date < today
        and TaskStatus(task.status) is not TaskStatus.DONE
    )
    if not overdue:
        raise ValidationError("There is no active overdue alert for this task")

    assigned = db.scalar(
        select(TaskAssignee.id).where(
            TaskAssignee.task_id == task.id, TaskAssignee.user_id == viewer.id
        )
    )
    if assigned is None:
        raise PermissionDeniedError("You can only dismiss alerts for tasks assigned to you")

    # Idempotent, concurrency-safe: one row per (task, user); re-dismissing just
    # re-stamps the due date it was made against.
    db.execute(
        pg_insert(AlertDismissal)
        .values(task_id=task.id, user_id=viewer.id, dismissed_due_date=task.due_date)
        .on_conflict_do_update(
            constraint="uq_dismissal_task_user",
            set_={"dismissed_due_date": task.due_date},
        )
    )
    db.flush()
