from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import Role
from app.schemas.common import NormalizedEmail

# --- login / tokens ----------------------------------------------------------


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# --- invitations -----------------------------------------------------------


class InvitationCreate(BaseModel):
    """A manager supplies only the email. Role is fixed to member server-side."""

    email: NormalizedEmail


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Role
    invited_by_id: uuid.UUID
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationCreated(InvitationOut):
    """Returned once, at creation time, with the raw accept link."""

    accept_url: str
    email_sent: bool


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=1)
    full_name: str = Field(min_length=1, max_length=255)
    # bcrypt only uses the first 72 bytes; reject longer rather than truncate.
    password: str = Field(min_length=8, max_length=72)
