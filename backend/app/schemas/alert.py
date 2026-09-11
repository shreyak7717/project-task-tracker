from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.enums import TaskPriority, TaskStatus


class AlertItem(BaseModel):
    id: uuid.UUID
    title: str
    project_id: uuid.UUID
    project_key: str
    status: TaskStatus
    priority: TaskPriority
    due_date: date
    days_overdue: int
    assigned_to_me: bool


class AlertsOut(BaseModel):
    count: int
    items: list[AlertItem]
