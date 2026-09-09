"""Authentication endpoints: login, token refresh, current user, invite accept."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from jose import JWTError
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.auth import (
    AcceptInvitationRequest,
    AccessToken,
    LoginRequest,
    RefreshRequest,
    TokenPair,
)
from app.schemas.user import UserOut
from app.security import (
    DUMMY_PASSWORD_HASH,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.services import invitations as invitation_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

_INVALID_LOGIN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
)
_INVALID_REFRESH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
)


def _issue_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, db: DbSession) -> TokenPair:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        # Spend the same time as a real verify so timing doesn't leak existence.
        verify_password(body.password, DUMMY_PASSWORD_HASH)
        raise _INVALID_LOGIN
    if not user.is_active or not verify_password(body.password, user.hashed_password):
        raise _INVALID_LOGIN
    return _issue_pair(user)


@router.post("/refresh", response_model=AccessToken)
def refresh(body: RefreshRequest, db: DbSession) -> AccessToken:
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise _INVALID_REFRESH from None
    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise _INVALID_REFRESH
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise _INVALID_REFRESH from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _INVALID_REFRESH
    return AccessToken(access_token=create_access_token(str(user.id), user.role))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post(
    "/invitations/accept",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
)
def accept_invitation(body: AcceptInvitationRequest, db: DbSession) -> TokenPair:
    user = invitation_service.accept_invitation(
        db, token=body.token, full_name=body.full_name, password=body.password
    )
    db.commit()
    return _issue_pair(user)
