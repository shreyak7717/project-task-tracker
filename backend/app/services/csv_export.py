"""CSV export of the filtered task list (brief goal 7).

Streams one row at a time so a large export doesn't buffer the whole file in
memory. Uses the same query builder as the list endpoint, minus pagination, so
the download always matches the filters the user is looking at.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Task, User
from app.schemas.task import TaskListParams
from app.services import task_query

_HEADER = [
    "project_key",
    "project_name",
    "title",
    "status",
    "priority",
    "assignees",
    "due_date",
    "created_at",
    "updated_at",
]


def _row(task: Task) -> list[str]:
    return [
        task.project.key,
        task.project.name,
        task.title,
        str(task.status),
        str(task.priority),
        "; ".join(sorted(a.user.full_name for a in task.assignees)),
        task.due_date.isoformat() if task.due_date else "",
        task.created_at.isoformat(),
        task.updated_at.isoformat(),
    ]


def stream_csv(db: Session, *, viewer: User, params: TaskListParams) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def take() -> str:
        chunk = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return chunk

    writer.writerow(_HEADER)
    yield take()

    for task in task_query.query_all_matching(db, viewer=viewer, params=params):
        writer.writerow(_row(task))
        yield take()


def filename() -> str:
    return f"tasks-{datetime.now(UTC):%Y-%m-%d}.csv"
