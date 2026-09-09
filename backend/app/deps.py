"""FastAPI dependencies for authentication and role checks.

The JWT is only a claim about who the caller is. Authorization always resolves
against the live database row: we load the ``User`` by the token's ``sub`` and
read ``user.role`` from that row, never from the token. So promoting/demoting or
deactivating a user takes effect on their next request, not when their token
finally expires.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db import get_db
from app.enums import Role
from app.models import User
from app.security import ACCESS_TOKEN_TYPE, decode_token

DbSession = Annotated[Session, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None:
        raise _UNAUTHORIZED
    try:
        payload = decode_token(creds.credentials)
    except JWTError:
        raise _UNAUTHORIZED from None

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise _UNAUTHORIZED

    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise _UNAUTHORIZED from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


def require_manager(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != Role.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Manager role required"
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
ManagerUser = Annotated[User, Depends(require_manager)]
