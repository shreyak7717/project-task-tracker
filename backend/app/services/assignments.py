"""Task assignment (brief goal 5).

Rules:
- Many-to-many: a task has any number of assignees, a person holds any number of
  tasks.
- Only a member of the task's project may be assigned to it.
- ``set_assignees`` validates the whole requested set before touching anything,
  so a single bad id rejects the replacement with no partial change.
- Every add/remove appends an ``ASSIGNED`` / ``UNASSIGNED`` event.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import TaskEventType
from app.models import Project, ProjectMembership, Task, TaskAssignee, User
from app.services import events
from app.services.errors import NotFoundError, ValidationError
from app.services.visibility import ensure_project_active


def _project_member_ids(db: Session, project_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        db.scalars(
            select(ProjectMembership.user_id).where(ProjectMembership.project_id == project_id)
        )
    )


def _users_by_id(db: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, User]:
    ids = list(ids)
    if not ids:
        return {}
    return {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))}


def _assignee_rows(db: Session, task: Task) -> list[TaskAssignee]:
    return list(db.scalars(select(TaskAssignee).where(TaskAssignee.task_id == task.id)))


def assignee_users(db: Session, task: Task) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(TaskAssignee, TaskAssignee.user_id == User.id)
            .where(TaskAssignee.task_id == task.id)
            .order_by(User.full_name)
        )
    )


def assign(db: Session, *, task: Task, user_id: uuid.UUID, actor: User) -> TaskAssignee:
    ensure_project_active(db, task.project_id)

    existing = db.scalar(
        select(TaskAssignee).where(TaskAssignee.task_id == task.id, TaskAssignee.user_id == user_id)
    )
    if existing is not None:
        return existing  # idempotent

    user = db.get(User, user_id)
    if user is None:
        raise ValidationError("Unknown user")
    if user.id not in _project_member_ids(db, task.project_id):
        raise ValidationError(f"{user.full_name} is not a member of this project")

    row = TaskAssignee(task_id=task.id, user_id=user.id)
    db.add(row)
    events.record(db, task=task, actor=actor, event_type=TaskEventType.ASSIGNED, new=user.full_name)
    db.flush()
    return row


def unassign(db: Session, *, task: Task, user_id: uuid.UUID, actor: User) -> None:
    ensure_project_active(db, task.project_id)

    row = db.scalar(
        select(TaskAssignee).where(TaskAssignee.task_id == task.id, TaskAssignee.user_id == user_id)
    )
    if row is None:
        raise NotFoundError("That user is not assigned to this task")

    user = db.get(User, user_id)
    db.delete(row)
    events.record(
        db,
        task=task,
        actor=actor,
        event_type=TaskEventType.UNASSIGNED,
        old=user.full_name if user else None,
    )
    db.flush()


def set_assignees(
    db: Session, *, task: Task, user_ids: Iterable[uuid.UUID], actor: User
) -> list[User]:
    """Replace the task's assignee set. Atomic: validate everything first."""
    ensure_project_active(db, task.project_id)

    requested = list(dict.fromkeys(user_ids))  # de-dupe, keep order

    users = _users_by_id(db, requested)
    unknown = [uid for uid in requested if uid not in users]
    if unknown:
        raise ValidationError(f"Unknown user id(s): {', '.join(str(u) for u in unknown)}")

    member_ids = _project_member_ids(db, task.project_id)
    outsiders = sorted(u.full_name for u in users.values() if u.id not in member_ids)
    if outsiders:
        raise ValidationError(f"Not members of this project: {', '.join(outsiders)}")

    # --- validated; apply the diff ---
    current = {row.user_id: row for row in _assignee_rows(db, task)}
    requested_set = set(requested)
    to_remove = set(current) - requested_set
    removed_users = _users_by_id(db, to_remove)

    for uid in requested:
        if uid not in current:
            db.add(TaskAssignee(task_id=task.id, user_id=uid))
            events.record(
                db,
                task=task,
                actor=actor,
                event_type=TaskEventType.ASSIGNED,
                new=users[uid].full_name,
            )
    for uid in to_remove:
        db.delete(current[uid])
        name = removed_users[uid].full_name if uid in removed_users else None
        events.record(db, task=task, actor=actor, event_type=TaskEventType.UNASSIGNED, old=name)

    db.flush()
    return assignee_users(db, task)


def unassign_from_project(
    db: Session, *, project: Project, user_id: uuid.UUID, actor: User | None = None
) -> None:
    """Drop every assignment this user holds on the project's tasks.

    Called when a member is removed from a project. ``actor=None`` marks the
    events as system-generated.
    """
    user = db.get(User, user_id)
    rows = list(
        db.scalars(
            select(TaskAssignee)
            .join(Task, TaskAssignee.task_id == Task.id)
            .where(Task.project_id == project.id, TaskAssignee.user_id == user_id)
        )
    )
    for row in rows:
        task = db.get(Task, row.task_id)
        db.delete(row)
        events.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskEventType.UNASSIGNED,
            old=user.full_name if user else None,
        )
    if rows:
        db.flush()
