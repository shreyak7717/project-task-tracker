"""The task status state machine (brief goal 4).

    Backlog -> In Progress -> In Review -> Done

plus: Blocked can be entered from In Progress or In Review and is left only by
unblocking (which returns the task to the status it was blocked from); a Done
task can be reopened to In Progress; a task with an unfinished blocking task
cannot move to Done.

``transition`` validates the move first (raising ``ValidationError`` with an
explanation the API passes straight through) and only then mutates the task and
appends a ``STATUS_CHANGED`` event. Illegal moves never touch the row.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.enums import TaskEventType, TaskStatus
from app.models import Task, User
from app.services import events
from app.services.errors import ValidationError

B, IP, IR, D, BL = (
    TaskStatus.BACKLOG,
    TaskStatus.IN_PROGRESS,
    TaskStatus.IN_REVIEW,
    TaskStatus.DONE,
    TaskStatus.BLOCKED,
)

ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    B: frozenset({IP}),
    IP: frozenset({B, IR, BL}),
    IR: frozenset({IP, D, BL}),
    D: frozenset({IP}),  # reopen
    BL: frozenset(),  # leave only via unblock
}

# Canonical order for presenting choices to the UI.
_ORDER = [B, IP, IR, D, BL]


def _is_unblock(task: Task, to_status: TaskStatus) -> bool:
    return (
        TaskStatus(task.status) is BL
        and task.blocked_from_status is not None
        and to_status is TaskStatus(task.blocked_from_status)
    )


def legal_targets(task: Task) -> set[TaskStatus]:
    """Every status this task could legally move to, ignoring dependency state."""
    current = TaskStatus(task.status)
    if current is BL:
        return {TaskStatus(task.blocked_from_status)} if task.blocked_from_status else set()
    return set(ALLOWED_TRANSITIONS[current])


def allowed_transitions_for(task: Task, *, has_unfinished_dependencies: bool) -> list[TaskStatus]:
    """What the interface should offer right now — only currently-legal moves."""
    targets = legal_targets(task)
    if has_unfinished_dependencies:
        targets.discard(D)
    return [s for s in _ORDER if s in targets]


def transition(
    db: Session,
    *,
    task: Task,
    to_status: TaskStatus,
    actor: User | None,
    unfinished_dependency_titles: Sequence[str] = (),
) -> None:
    from_status = TaskStatus(task.status)
    to_status = TaskStatus(to_status)

    if to_status is from_status:
        raise ValidationError(f"Task is already {from_status.value.replace('_', ' ')}.")

    if from_status is BL:
        if not _is_unblock(task, to_status):
            back_to = task.blocked_from_status or "its previous status"
            raise ValidationError(
                f"A blocked task can only be unblocked (returned to {back_to})."
            )
    elif to_status not in ALLOWED_TRANSITIONS[from_status]:
        raise ValidationError(
            f"Illegal transition {from_status.value} → {to_status.value}."
        )

    if to_status is D and unfinished_dependency_titles:
        titles = list(unfinished_dependency_titles)
        plural = "s" if len(titles) != 1 else ""
        raise ValidationError(
            f"Cannot move to Done: blocked by {len(titles)} unfinished task{plural}: "
            f"{', '.join(titles)}."
        )

    # --- validated; apply ---
    if to_status is BL:
        task.blocked_from_status = from_status
    elif _is_unblock(task, to_status):
        task.blocked_from_status = None

    if to_status is D:
        task.completed_at = datetime.now(UTC)
    elif from_status is D:
        task.completed_at = None  # reopened

    task.status = to_status
    events.record(
        db,
        task=task,
        actor=actor,
        event_type=TaskEventType.STATUS_CHANGED,
        field="status",
        old=from_status,
        new=to_status,
    )
    db.flush()
