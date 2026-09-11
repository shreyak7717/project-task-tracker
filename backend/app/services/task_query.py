"""The cross-project task list (brief goal 6).

One query builder, used by the list endpoint, the CSV export, and
"assigned to me". Search, every filter, sorting, pagination and the total count
all run in the database — nothing loads the task table into memory to filter it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.enums import TaskStatus
from app.models import Project, Task, TaskAssignee, User
from app.schemas.task import TaskListParams
from app.services.visibility import task_visibility_clause


@dataclass
class Page:
    items: list[Task]
    total: int
    page: int
    page_size: int
    pages: int


_PRIORITY_RANK = case(
    (Task.priority == "urgent", 4),
    (Task.priority == "high", 3),
    (Task.priority == "medium", 2),
    (Task.priority == "low", 1),
    else_=0,
)

_SORT_EXPR = {
    "due_date": Task.due_date,
    "priority": _PRIORITY_RANK,
    "updated_at": Task.updated_at,
}

_EAGER = (
    selectinload(Task.project),
    selectinload(Task.assignees).selectinload(TaskAssignee.user),
)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filtered(db: Session, *, viewer: User, params: TaskListParams) -> Select:
    stmt = select(Task).join(Project, Task.project_id == Project.id)

    visible = task_visibility_clause(db, viewer)
    if visible is not None:
        stmt = stmt.where(visible)

    if not params.include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))

    if params.project_id is not None:
        stmt = stmt.where(Task.project_id == params.project_id)

    if params.q:
        like = f"%{_escape_like(params.q)}%"
        stmt = stmt.where(
            or_(
                Task.title.ilike(like, escape="\\"),
                Task.description.ilike(like, escape="\\"),
            )
        )

    if params.status:
        stmt = stmt.where(Task.status.in_([s.value for s in params.status]))
    if params.priority:
        stmt = stmt.where(Task.priority.in_([p.value for p in params.priority]))

    if params.assignee_id is not None:
        stmt = stmt.where(
            Task.id.in_(
                select(TaskAssignee.task_id).where(TaskAssignee.user_id == params.assignee_id)
            )
        )
    if params.unassigned:
        stmt = stmt.where(~select(TaskAssignee.id).where(TaskAssignee.task_id == Task.id).exists())

    if params.overdue:
        stmt = stmt.where(
            and_(Task.due_date < func.current_date(), Task.status != TaskStatus.DONE.value)
        )

    return stmt


def _sorted(stmt: Select, params: TaskListParams) -> Select:
    expr = _SORT_EXPR[params.sort]
    ordered = expr.desc() if params.order == "desc" else expr.asc()
    if params.sort == "due_date":
        ordered = ordered.nulls_last()
    return stmt.order_by(ordered, Task.id)  # id keeps pagination stable


def query_tasks(db: Session, *, viewer: User, params: TaskListParams) -> Page:
    base = _filtered(db, viewer=viewer, params=params)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    offset = (params.page - 1) * params.page_size
    stmt = _sorted(base, params).options(*_EAGER).limit(params.page_size).offset(offset)
    items = list(db.scalars(stmt))

    pages = (total + params.page_size - 1) // params.page_size if total else 0
    return Page(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=pages,
    )


def query_all_matching(db: Session, *, viewer: User, params: TaskListParams) -> list[Task]:
    """Everything matching the filters, unpaginated — for CSV export."""
    stmt = _sorted(_filtered(db, viewer=viewer, params=params), params).options(*_EAGER)
    return list(db.scalars(stmt))
