"""Task CRUD, dependencies, comments, and the timeline read.

Status changes go through app.services.lifecycle; this module gathers the
unfinished-dependency context that the state machine needs. Every mutation that
changes a task appends a TaskEvent via app.services.events.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.enums import TaskEventType, TaskStatus
from app.models import Project, Task, TaskDependency, TaskEvent, User
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import events, lifecycle
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.visibility import can_see_project

_EDITABLE_FIELDS = ("title", "description", "priority", "due_date")


# --- lookups -------------------------------------------------------------


def get_visible_task_or_404(db: Session, *, user: User, task_id: uuid.UUID) -> Task:
    task = db.get(Task, task_id)
    if task is not None:
        project = db.get(Project, task.project_id)
        if project is not None and can_see_project(db, user, project):
            return task
    raise NotFoundError("Task not found")


def list_for_project(db: Session, *, project: Project) -> list[Task]:
    return list(
        db.scalars(
            select(Task)
            .where(Task.project_id == project.id)
            .order_by(Task.created_at.desc())
        )
    )


def dependencies_of(db: Session, task: Task) -> list[Task]:
    """The tasks that block ``task`` (any status)."""
    return list(
        db.scalars(
            select(Task)
            .join(TaskDependency, TaskDependency.depends_on_task_id == Task.id)
            .where(TaskDependency.task_id == task.id)
            .order_by(Task.title)
        )
    )


def unfinished_dependencies_of(db: Session, task: Task) -> list[Task]:
    return [t for t in dependencies_of(db, task) if TaskStatus(t.status) is not TaskStatus.DONE]


# --- create / update / delete -----------------------------------------


def create_task(db: Session, *, project: Project, data: TaskCreate, actor: User) -> Task:
    task = Task(
        project_id=project.id,
        title=data.title,
        description=data.description,
        priority=data.priority,
        due_date=data.due_date,
        status=TaskStatus.BACKLOG,
        created_by_id=actor.id,
    )
    db.add(task)
    db.flush()

    events.record(db, task=task, actor=actor, event_type=TaskEventType.CREATED)
    for dep_id in dict.fromkeys(data.depends_on_task_ids):  # de-dupe, keep order
        add_dependency(db, task=task, depends_on_task_id=dep_id, actor=actor)

    db.flush()
    return task


def update_task(db: Session, *, task: Task, data: TaskUpdate, actor: User) -> Task:
    changes: dict[str, tuple[object, object]] = {}
    for field in _EDITABLE_FIELDS:
        if field not in data.model_fields_set:
            continue  # omitted -> leave untouched (distinct from an explicit null)
        new = getattr(data, field)
        old = getattr(task, field)
        if field == "priority" and new is None:
            raise ValidationError("priority cannot be cleared")
        changes[field] = (old, new)
        setattr(task, field, new)

    events.record_field_changes(db, task=task, actor=actor, changes=changes)
    db.flush()
    return task


def delete_task(db: Session, *, task: Task) -> None:
    # Dependencies, assignees and events cascade via the FKs.
    db.delete(task)
    db.flush()


# --- status -----------------------------------------------------------


def transition_task(
    db: Session, *, task: Task, to_status: TaskStatus, actor: User
) -> Task:
    unfinished = unfinished_dependencies_of(db, task)
    lifecycle.transition(
        db,
        task=task,
        to_status=to_status,
        actor=actor,
        unfinished_dependency_titles=[t.title for t in unfinished],
    )
    return task


def allowed_transitions(db: Session, task: Task) -> Sequence[TaskStatus]:
    return lifecycle.allowed_transitions_for(
        task, has_unfinished_dependencies=bool(unfinished_dependencies_of(db, task))
    )


# --- dependencies -----------------------------------------------------


def add_dependency(
    db: Session, *, task: Task, depends_on_task_id: uuid.UUID, actor: User
) -> TaskDependency:
    if depends_on_task_id == task.id:
        raise ValidationError("A task cannot block itself")

    blocker = db.get(Task, depends_on_task_id)
    if blocker is None:
        raise NotFoundError("Blocking task not found")
    if blocker.project_id != task.project_id:
        raise ValidationError("A blocking task must be in the same project")

    if db.scalar(
        select(TaskDependency.id).where(
            TaskDependency.task_id == task.id,
            TaskDependency.depends_on_task_id == blocker.id,
        )
    ):
        raise ConflictError("That dependency already exists")

    if db.scalar(
        select(TaskDependency.id).where(
            TaskDependency.task_id == blocker.id,
            TaskDependency.depends_on_task_id == task.id,
        )
    ):
        raise ValidationError(
            f"{blocker.title!r} is already blocked by this task - that would be circular"
        )

    dependency = TaskDependency(task_id=task.id, depends_on_task_id=blocker.id)
    db.add(dependency)
    events.record(
        db,
        task=task,
        actor=actor,
        event_type=TaskEventType.DEPENDENCY_ADDED,
        new=blocker.title,
    )
    db.flush()
    return dependency


def remove_dependency(
    db: Session, *, task: Task, depends_on_task_id: uuid.UUID, actor: User
) -> None:
    dependency = db.scalar(
        select(TaskDependency).where(
            TaskDependency.task_id == task.id,
            TaskDependency.depends_on_task_id == depends_on_task_id,
        )
    )
    if dependency is None:
        raise NotFoundError("That dependency does not exist")

    blocker = db.get(Task, depends_on_task_id)
    db.delete(dependency)
    events.record(
        db,
        task=task,
        actor=actor,
        event_type=TaskEventType.DEPENDENCY_REMOVED,
        old=blocker.title if blocker else None,
    )
    db.flush()


# --- comments / timeline --------------------------------------------


def add_comment(db: Session, *, task: Task, body: str, actor: User) -> TaskEvent:
    event = events.record(
        db, task=task, actor=actor, event_type=TaskEventType.COMMENTED, body=body
    )
    db.flush()
    return event


def get_timeline(db: Session, *, task: Task) -> list[TaskEvent]:
    return list(
        db.scalars(
            select(TaskEvent)
            .options(selectinload(TaskEvent.actor))
            .where(TaskEvent.task_id == task.id)
            .order_by(TaskEvent.created_at, TaskEvent.id)
        )
    )
