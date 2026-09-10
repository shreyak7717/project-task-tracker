"""The task state machine, exercised directly against the service."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.enums import TaskStatus as S
from app.models import TaskEvent
from app.services import lifecycle
from app.services.errors import ValidationError


def test_backlog_to_in_progress_is_allowed(db, make_task, manager):
    task = make_task(status=S.BACKLOG)
    lifecycle.transition(db, task=task, to_status=S.IN_PROGRESS, actor=manager)
    assert task.status == S.IN_PROGRESS


def test_backlog_straight_to_done_is_rejected_and_leaves_the_task_alone(db, make_task, manager):
    task = make_task(status=S.BACKLOG)
    with pytest.raises(ValidationError, match="Illegal transition"):
        lifecycle.transition(db, task=task, to_status=S.DONE, actor=manager)
    assert task.status == S.BACKLOG


def test_cannot_enter_blocked_from_backlog(db, make_task, manager):
    task = make_task(status=S.BACKLOG)
    with pytest.raises(ValidationError, match="Illegal transition"):
        lifecycle.transition(db, task=task, to_status=S.BLOCKED, actor=manager)


def test_entering_done_sets_completed_at_reopen_clears_it(db, make_task, manager):
    task = make_task(status=S.IN_REVIEW)
    lifecycle.transition(db, task=task, to_status=S.DONE, actor=manager)
    assert task.status == S.DONE and task.completed_at is not None

    lifecycle.transition(db, task=task, to_status=S.IN_PROGRESS, actor=manager)
    assert task.status == S.IN_PROGRESS and task.completed_at is None


def test_block_then_unblock_returns_to_origin(db, make_task, manager):
    task = make_task(status=S.IN_REVIEW)
    lifecycle.transition(db, task=task, to_status=S.BLOCKED, actor=manager)
    assert task.status == S.BLOCKED
    assert task.blocked_from_status == S.IN_REVIEW

    lifecycle.transition(db, task=task, to_status=S.IN_REVIEW, actor=manager)
    assert task.status == S.IN_REVIEW
    assert task.blocked_from_status is None


def test_blocked_task_cannot_jump_elsewhere(db, make_task, manager):
    task = make_task(status=S.IN_PROGRESS)
    lifecycle.transition(db, task=task, to_status=S.BLOCKED, actor=manager)
    with pytest.raises(ValidationError, match="unblocked"):
        lifecycle.transition(db, task=task, to_status=S.DONE, actor=manager)


def test_done_is_refused_while_a_blocking_task_is_unfinished(db, make_task, manager):
    task = make_task(status=S.IN_REVIEW)
    with pytest.raises(ValidationError, match="blocked by 2 unfinished tasks: Set up CI, Write docs"):
        lifecycle.transition(
            db,
            task=task,
            to_status=S.DONE,
            actor=manager,
            unfinished_dependency_titles=["Set up CI", "Write docs"],
        )
    assert task.status == S.IN_REVIEW


def test_moving_to_the_same_status_is_rejected(db, make_task, manager):
    task = make_task(status=S.BACKLOG)
    with pytest.raises(ValidationError, match="already"):
        lifecycle.transition(db, task=task, to_status=S.BACKLOG, actor=manager)


def test_allowed_transitions_drops_done_when_dependencies_unfinished(db, make_task):
    task = make_task(status=S.IN_REVIEW)
    free = lifecycle.allowed_transitions_for(task, has_unfinished_dependencies=False)
    blocked = lifecycle.allowed_transitions_for(task, has_unfinished_dependencies=True)
    assert S.DONE in free
    assert S.DONE not in blocked


def test_allowed_transitions_for_a_blocked_task_is_just_unblock(db, make_task, manager):
    task = make_task(status=S.IN_PROGRESS)
    lifecycle.transition(db, task=task, to_status=S.BLOCKED, actor=manager)
    assert lifecycle.allowed_transitions_for(task, has_unfinished_dependencies=False) == [
        S.IN_PROGRESS
    ]


def test_every_status_change_is_recorded_with_actor_and_values(db, make_task, manager):
    task = make_task(status=S.BACKLOG)
    lifecycle.transition(db, task=task, to_status=S.IN_PROGRESS, actor=manager)
    event = db.scalar(select(TaskEvent).where(TaskEvent.task_id == task.id))
    assert event.event_type == "status_changed"
    assert event.field == "status"
    assert event.old_value == "backlog"
    assert event.new_value == "in_progress"
    assert event.actor_id == manager.id
