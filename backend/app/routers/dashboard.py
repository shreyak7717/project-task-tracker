"""The dashboard landing view (brief goal 8), scoped to the caller's projects."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from app.deps import CurrentUser, DbSession
from app.schemas.dashboard import DashboardOut
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: DbSession, user: CurrentUser, scope: Literal["team", "mine"] = "team"
) -> DashboardOut:
    return DashboardOut.model_validate(
        dashboard_service.get_dashboard(db, viewer=user, mine_only=scope == "mine")
    )
