"""Overdue-alert endpoints (brief goal 10).

The one UTC reference for the request is fixed here and passed into the service,
so the list, the count, and the days-overdue values are all consistent.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status

from app.deps import CurrentUser, DbSession
from app.schemas.alert import AlertItem, AlertsOut
from app.services import alerts as alert_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=AlertsOut)
def list_alerts(db: DbSession, user: CurrentUser) -> AlertsOut:
    today = datetime.now(UTC).date()
    tasks = alert_service.list_alerts(db, viewer=user, today=today)
    items = [
        AlertItem(
            id=task.id,
            title=task.title,
            project_id=task.project_id,
            project_key=task.project.key,
            status=task.status,
            priority=task.priority,
            due_date=task.due_date,
            days_overdue=(today - task.due_date).days,
            assigned_to_me=any(a.user_id == user.id for a in task.assignees),
        )
        for task in tasks
    ]
    return AlertsOut(count=len(items), items=items)


@router.get("/count")
def alert_count(db: DbSession, user: CurrentUser) -> dict[str, int]:
    today = datetime.now(UTC).date()
    return {"count": alert_service.alert_count(db, viewer=user, today=today)}


@router.post(
    "/{task_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def dismiss_alert(task_id: uuid.UUID, db: DbSession, user: CurrentUser):
    alert_service.dismiss(
        db, viewer=user, task_id=task_id, today=datetime.now(UTC).date()
    )
    db.commit()
