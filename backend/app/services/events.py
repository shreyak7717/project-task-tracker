"""The task timeline — the only place ``TaskEvent`` rows are created.

``TaskEvent`` is append-only: nothing in the codebase updates or deletes one.
That is the entire guarantee behind "history you cannot rewrite" (brief goal 9),
so every write path that changes a task routes through here.

Services add events to the session; the calling router commits.
"""

from __future__ import annotations

import datetime as dt
import enum
from typing import Any

from sqlalchemy.orm import Session

from app.enums import TaskEventType
from app.models import Task, TaskEvent, User


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, enum.Enum):
        return str(value.value)
    if isinstance(value, dt.date | dt.datetime):
        return value.isoformat()
    return str(value)


def record(
    db: Session,
    *,
    task: Task,
    actor: User | None,
    event_type: TaskEventType,
    field: str | None = None,
    old: Any = None,
    new: Any = None,
    body: str | None = None,
) -> TaskEvent:
    """Append one event. ``actor=None`` marks a system-generated entry."""
    event = TaskEvent(
        task_id=task.id,
        actor_id=actor.id if actor is not None else None,
        event_type=event_type,
        field=field,
        old_value=_stringify(old),
        new_value=_stringify(new),
        body=body,
    )
    db.add(event)
    return event


def record_field_change(
    db: Session, *, task: Task, actor: User | None, field: str, old: Any, new: Any
) -> TaskEvent | None:
    """Record a ``FIELD_CHANGED`` event, or nothing if the value is unchanged."""
    if _stringify(old) == _stringify(new):
        return None
    return record(
        db,
        task=task,
        actor=actor,
        event_type=TaskEventType.FIELD_CHANGED,
        field=field,
        old=old,
        new=new,
    )


def record_field_changes(
    db: Session,
    *,
    task: Task,
    actor: User | None,
    changes: dict[str, tuple[Any, Any]],
) -> list[TaskEvent]:
    """``changes`` maps field name -> (old, new). No-op fields are skipped."""
    recorded: list[TaskEvent] = []
    for field, (old, new) in changes.items():
        event = record_field_change(db, task=task, actor=actor, field=field, old=old, new=new)
        if event is not None:
            recorded.append(event)
    return recorded
