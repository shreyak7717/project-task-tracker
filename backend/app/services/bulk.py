"""Bulk actions (brief goal 7).

Apply one change — a status move, an assignee replacement, or a new due date —
to many tasks. Each task runs in its own SAVEPOINT: a failure rolls back only
that task and is reported; the rest still apply. Nothing here re-implements a
rule — it dispatches to the task / lifecycle / assignment services, so the
blocking-task check, legal-transition check and assignee-must-be-a-member check
all still hold.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models import User
from app.schemas.task import (
    BulkChange,
    BulkItemResult,
    BulkResult,
    BulkSetAssignees,
    BulkSetDueDate,
    BulkTransition,
    TaskUpdate,
)
from app.services import assignments, tasks
from app.services.errors import ServiceError


def _apply_one(db: Session, *, task, change: BulkChange, actor: User) -> None:
    if isinstance(change, BulkTransition):
        tasks.transition_task(db, task=task, to_status=change.to_status, actor=actor)
    elif isinstance(change, BulkSetAssignees):
        assignments.set_assignees(db, task=task, user_ids=change.user_ids, actor=actor)
    elif isinstance(change, BulkSetDueDate):
        # Passing due_date explicitly puts it in model_fields_set, so update_task
        # treats None as "clear it" rather than "leave alone".
        tasks.update_task(db, task=task, data=TaskUpdate(due_date=change.due_date), actor=actor)
    else:  # pragma: no cover - discriminated union makes this unreachable
        raise ServiceError(f"Unknown bulk change: {change!r}")


def apply_bulk(
    db: Session, *, viewer: User, task_ids: Sequence[uuid.UUID], change: BulkChange
) -> BulkResult:
    results: list[BulkItemResult] = []
    for task_id in dict.fromkeys(task_ids):  # de-dupe, keep order
        savepoint = db.begin_nested()
        try:
            task = tasks.get_visible_task_or_404(db, user=viewer, task_id=task_id)
            _apply_one(db, task=task, change=change, actor=viewer)
            savepoint.commit()
            results.append(BulkItemResult(task_id=task_id, ok=True))
        except ServiceError as exc:
            savepoint.rollback()
            results.append(BulkItemResult(task_id=task_id, ok=False, error=exc.detail))

    succeeded = sum(1 for r in results if r.ok)
    return BulkResult(results=results, succeeded=succeeded, failed=len(results) - succeeded)
