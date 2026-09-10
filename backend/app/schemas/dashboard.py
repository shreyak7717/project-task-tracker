from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.enums import TaskStatus
from app.schemas.user import UserOut


class DashboardHeadline(BaseModel):
    open: int
    overdue: int
    due_this_week: int
    completed_this_week: int


class StatusCount(BaseModel):
    status: TaskStatus
    count: int


class AssigneeCount(BaseModel):
    user: UserOut | None  # None = the unassigned bucket
    count: int


class WeekCompletions(BaseModel):
    week_start: date  # first day of the rolling 7-day window
    count: int


class DashboardOut(BaseModel):
    headline: DashboardHeadline
    by_status: list[StatusCount]
    by_assignee: list[AssigneeCount]
    completions_last_8_weeks: list[WeekCompletions]
