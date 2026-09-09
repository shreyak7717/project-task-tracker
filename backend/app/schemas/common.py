"""Shared field types and base models for request/response schemas."""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, EmailStr


def _normalize_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


# Use everywhere an email arrives from a client, so lookups and the unique
# constraint on users.email are always comparing the same normalised form.
NormalizedEmail = Annotated[EmailStr, BeforeValidator(_normalize_email)]
