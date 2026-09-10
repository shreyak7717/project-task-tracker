"""Cross-project task views (goal 6) and bulk actions (goal 7).

Registered BEFORE routers.tasks so the literal ``/api/tasks/export`` and
``/api/tasks/bulk`` paths are matched before ``/api/tasks/{task_id}``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.deps import CurrentUser, DbSession
from app.models import Task
from app.schemas.task import (
    BulkRequest,
    BulkResult,
    TaskListItem,
    TaskListParams,
    TaskOut,
    TaskPage,
)
from app.schemas.user import UserOut
from app.services import bulk as bulk_service
from app.services import csv_export, task_query

router = APIRouter(tags=["tasks"])

_Params = Annotated[TaskListParams, Query()]


def _item(task: Task) -> TaskListItem:
    return TaskListItem(
        **TaskOut.model_validate(task).model_dump(),
        project_key=task.project.key,
        project_name=task.project.name,
        assignees=[UserOut.model_validate(a.user) for a in task.assignees],
    )


def _page(page: task_query.Page) -> TaskPage:
    return TaskPage(
        items=[_item(t) for t in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        pages=page.pages,
    )


@router.get("/api/tasks", response_model=TaskPage)
def list_tasks(db: DbSession, user: CurrentUser, params: _Params) -> TaskPage:
    return _page(task_query.query_tasks(db, viewer=user, params=params))


@router.get("/api/me/tasks", response_model=TaskPage)
def my_tasks(db: DbSession, user: CurrentUser, params: _Params) -> TaskPage:
    scoped = params.model_copy(update={"assignee_id": user.id, "unassigned": False})
    return _page(task_query.query_tasks(db, viewer=user, params=scoped))


@router.get("/api/tasks/export")
def export_tasks(db: DbSession, user: CurrentUser, params: _Params) -> StreamingResponse:
    return StreamingResponse(
        csv_export.stream_csv(db, viewer=user, params=params),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{csv_export.filename()}"'
        },
    )


@router.post("/api/tasks/bulk", response_model=BulkResult)
def bulk_apply(body: BulkRequest, db: DbSession, user: CurrentUser) -> BulkResult:
    result = bulk_service.apply_bulk(
        db, viewer=user, task_ids=body.task_ids, change=body.change
    )
    db.commit()
    return result
