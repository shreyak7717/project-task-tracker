from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import TaskEventType, TaskPriority, TaskStatus
from app.schemas.user import UserOut


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    depends_on_task_ids: list[uuid.UUID] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    """Only the fields present in the request are changed. ``due_date: null``
    explicitly clears the date; omitting the key leaves it untouched (the
    service inspects ``model_fields_set`` to tell the two apart)."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    priority: TaskPriority | None = None
    due_date: date | None = None


class TransitionRequest(BaseModel):
    to_status: TaskStatus


class DependencyCreate(BaseModel):
    depends_on_task_id: uuid.UUID


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class TaskRef(BaseModel):
    """Compact reference to a task, for dependency lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: TaskStatus


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    blocked_from_status: TaskStatus | None
    due_date: date | None
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class TaskDetailOut(TaskOut):
    dependencies: list[TaskRef] = Field(default_factory=list)
    # True when a move to Done is currently disallowed only because a blocking
    # task is unfinished — lets the UI show a specific hint.
    blocked_by_unfinished_dependency: bool = False
    allowed_transitions: list[TaskStatus] = Field(default_factory=list)


class TaskEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: TaskEventType
    field: str | None
    old_value: str | None
    new_value: str | None
    body: str | None
    created_at: datetime
    actor: UserOut | None


# --- assignment ----------------------------------------------------------


class AssigneesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_ids: list[uuid.UUID] = Field(default_factory=list)


# --- cross-project list (goal 6) --------------------------------------


class TaskListItem(TaskOut):
    project_key: str
    project_name: str
    assignees: list[UserOut] = Field(default_factory=list)


class TaskListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=200)
    project_id: uuid.UUID | None = None
    status: list[TaskStatus] | None = None
    priority: list[TaskPriority] | None = None
    assignee_id: uuid.UUID | None = None
    unassigned: bool = False
    overdue: bool = False
    sort: Literal["due_date", "priority", "updated_at"] = "updated_at"
    order: Literal["asc", "desc"] = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class TaskPage(BaseModel):
    items: list[TaskListItem]
    total: int
    page: int
    page_size: int
    pages: int


# --- bulk actions (goal 7) -------------------------------------------


class BulkTransition(BaseModel):
    kind: Literal["transition"]
    to_status: TaskStatus


class BulkSetAssignees(BaseModel):
    kind: Literal["set_assignees"]
    user_ids: list[uuid.UUID] = Field(default_factory=list)


class BulkSetDueDate(BaseModel):
    kind: Literal["set_due_date"]
    due_date: date | None = None


BulkChange = Annotated[
    BulkTransition | BulkSetAssignees | BulkSetDueDate,
    Field(discriminator="kind"),
]


class BulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    change: BulkChange


class BulkItemResult(BaseModel):
    task_id: uuid.UUID
    ok: bool
    error: str | None = None


class BulkResult(BaseModel):
    results: list[BulkItemResult]
    succeeded: int
    failed: int

