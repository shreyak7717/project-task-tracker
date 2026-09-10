"""Task endpoints: CRUD, status transitions, dependencies, comments, timeline.

Access: anyone who can see the task's project (a member of it, or any manager)
may read and edit tasks and move their status. Only a manager may delete a task.
A task in a project the caller cannot see returns 404.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.deps import CurrentUser, DbSession, ManagerUser
from app.models import Task
from app.schemas.task import (
    AssigneesUpdate,
    CommentCreate,
    DependencyCreate,
    TaskCreate,
    TaskDetailOut,
    TaskEventOut,
    TaskOut,
    TaskRef,
    TaskUpdate,
    TransitionRequest,
)
from app.schemas.user import UserOut
from app.services import assignments as assignment_service
from app.services import tasks as task_service
from app.services.lifecycle import allowed_transitions_for
from app.services.visibility import get_visible_project_or_404

router = APIRouter(tags=["tasks"])


def _detail(db: DbSession, task: Task) -> TaskDetailOut:
    deps = task_service.dependencies_of(db, task)
    has_unfinished = any(d.status != "done" for d in deps)
    return TaskDetailOut(
        **TaskOut.model_validate(task).model_dump(),
        assignees=[UserOut.model_validate(u) for u in assignment_service.assignee_users(db, task)],
        dependencies=[TaskRef.model_validate(d) for d in deps],
        blocked_by_unfinished_dependency=has_unfinished,
        allowed_transitions=allowed_transitions_for(
            task, has_unfinished_dependencies=has_unfinished
        ),
    )


# --- collection under a project -------------------------------------


@router.post(
    "/api/projects/{project_id}/tasks",
    response_model=TaskDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    project_id: uuid.UUID, body: TaskCreate, db: DbSession, user: CurrentUser
) -> TaskDetailOut:
    project = get_visible_project_or_404(db, user, project_id)
    task = task_service.create_task(db, project=project, data=body, actor=user)
    db.commit()
    db.refresh(task)
    return _detail(db, task)


@router.get("/api/projects/{project_id}/tasks", response_model=list[TaskOut])
def list_project_tasks(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> list[Task]:
    project = get_visible_project_or_404(db, user, project_id)
    return task_service.list_for_project(db, project=project)


# --- single task ----------------------------------------------------


@router.get("/api/tasks/{task_id}", response_model=TaskDetailOut)
def get_task(task_id: uuid.UUID, db: DbSession, user: CurrentUser) -> TaskDetailOut:
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    return _detail(db, task)


@router.patch("/api/tasks/{task_id}", response_model=TaskDetailOut)
def update_task(
    task_id: uuid.UUID, body: TaskUpdate, db: DbSession, user: CurrentUser
) -> TaskDetailOut:
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    task_service.update_task(db, task=task, data=body, actor=user)
    db.commit()
    db.refresh(task)
    return _detail(db, task)


@router.delete(
    "/api/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_task(task_id: uuid.UUID, db: DbSession, manager: ManagerUser):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task_service.delete_task(db, task=task)
    db.commit()


@router.post("/api/tasks/{task_id}/transition", response_model=TaskDetailOut)
def transition_task(
    task_id: uuid.UUID, body: TransitionRequest, db: DbSession, user: CurrentUser
) -> TaskDetailOut:
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    task_service.transition_task(db, task=task, to_status=body.to_status, actor=user)
    db.commit()
    db.refresh(task)
    return _detail(db, task)


# --- dependencies -------------------------------------------------


@router.post(
    "/api/tasks/{task_id}/dependencies",
    response_model=TaskDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def add_dependency(
    task_id: uuid.UUID, body: DependencyCreate, db: DbSession, user: CurrentUser
) -> TaskDetailOut:
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    task_service.add_dependency(
        db, task=task, depends_on_task_id=body.depends_on_task_id, actor=user
    )
    db.commit()
    db.refresh(task)
    return _detail(db, task)


@router.delete(
    "/api/tasks/{task_id}/dependencies/{dep_task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remove_dependency(task_id: uuid.UUID, dep_task_id: uuid.UUID, db: DbSession, user: CurrentUser):
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    task_service.remove_dependency(db, task=task, depends_on_task_id=dep_task_id, actor=user)
    db.commit()


# --- assignees ---------------------------------------------------
#
# Caller must be able to see the task (a project member, or any manager). Each
# target assignee must be a member of the task's project — enforced by the
# service, not here.


@router.put("/api/tasks/{task_id}/assignees", response_model=TaskDetailOut)
def set_assignees(
    task_id: uuid.UUID, body: AssigneesUpdate, db: DbSession, user: CurrentUser
) -> TaskDetailOut:
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    assignment_service.set_assignees(db, task=task, user_ids=body.user_ids, actor=user)
    db.commit()
    db.refresh(task)
    return _detail(db, task)


@router.post(
    "/api/tasks/{task_id}/assignees/{user_id}",
    response_model=TaskDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def add_assignee(
    task_id: uuid.UUID, user_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> TaskDetailOut:
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    assignment_service.assign(db, task=task, user_id=user_id, actor=user)
    db.commit()
    db.refresh(task)
    return _detail(db, task)


@router.delete(
    "/api/tasks/{task_id}/assignees/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remove_assignee(task_id: uuid.UUID, user_id: uuid.UUID, db: DbSession, user: CurrentUser):
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    assignment_service.unassign(db, task=task, user_id=user_id, actor=user)
    db.commit()


# --- comments / timeline ---------------------------------------


@router.post(
    "/api/tasks/{task_id}/comments",
    response_model=TaskEventOut,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    task_id: uuid.UUID, body: CommentCreate, db: DbSession, user: CurrentUser
) -> TaskEventOut:
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    event = task_service.add_comment(db, task=task, body=body.body, actor=user)
    db.commit()
    db.refresh(event)
    return event


@router.get("/api/tasks/{task_id}/timeline", response_model=list[TaskEventOut])
def get_timeline(task_id: uuid.UUID, db: DbSession, user: CurrentUser) -> list[TaskEventOut]:
    task = task_service.get_visible_task_or_404(db, user=user, task_id=task_id)
    return task_service.get_timeline(db, task=task)
