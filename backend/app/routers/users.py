"""Manager-only user administration: issuing and listing invitations, and
listing existing users (used later by project-membership and assignee pickers).

There is intentionally no endpoint that creates a user directly — accounts only
come into existence through the invitation accept flow in routers/auth.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.deps import DbSession, ManagerUser
from app.enums import Role
from app.models import Invitation, User
from app.schemas.auth import InvitationCreate, InvitationCreated, InvitationOut
from app.schemas.user import UserOut
from app.services import invitations as invitation_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post(
    "/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    body: InvitationCreate, db: DbSession, manager: ManagerUser
) -> InvitationCreated:
    invitation, raw_token = invitation_service.create_invitation(
        db, email=body.email, invited_by=manager
    )
    db.commit()
    return InvitationCreated(
        accept_url=invitation_service.build_accept_url(raw_token),
        **InvitationOut.model_validate(invitation).model_dump(),
    )


@router.get("/invitations", response_model=list[InvitationOut])
def list_invitations(
    db: DbSession,
    manager: ManagerUser,
    status_: Literal["pending", "accepted", "expired", "all"] = Query("pending", alias="status"),
) -> list[Invitation]:
    now = datetime.now(UTC)
    stmt = select(Invitation).order_by(Invitation.created_at.desc())
    if status_ == "pending":
        stmt = stmt.where(Invitation.accepted_at.is_(None), Invitation.expires_at > now)
    elif status_ == "accepted":
        stmt = stmt.where(Invitation.accepted_at.is_not(None))
    elif status_ == "expired":
        stmt = stmt.where(Invitation.accepted_at.is_(None), Invitation.expires_at <= now)
    return list(db.scalars(stmt))


@router.get("", response_model=list[UserOut])
def list_users(
    db: DbSession, manager: ManagerUser, role: Role | None = None
) -> list[User]:
    stmt = select(User).order_by(User.full_name)
    if role is not None:
        stmt = stmt.where(User.role == role)
    return list(db.scalars(stmt))
