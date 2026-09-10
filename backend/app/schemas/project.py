from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.user import UserOut

# 2-10 chars, starts with a letter, uppercase letters/digits only (e.g. "ACME", "WEB2").
_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    owner_id: uuid.UUID

    @field_validator("key", mode="before")
    @classmethod
    def _upper(cls, v: object) -> object:
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("key")
    @classmethod
    def _valid_key(cls, v: str) -> str:
        if not _KEY_PATTERN.match(v):
            raise ValueError(
                "key must be 2-10 characters: uppercase letters/digits, starting with a letter"
            )
        return v


class ProjectUpdate(BaseModel):
    """All fields optional. The key is immutable after creation (task references
    like ACME-4 depend on it)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    owner_id: uuid.UUID | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str
    owner_id: uuid.UUID
    owner: UserOut
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class ProjectMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    user: UserOut
    member_since: datetime = Field(validation_alias="created_at")
