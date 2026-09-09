"""Issuing and accepting member invitations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import Role
from app.models import Invitation, User
from app.security import generate_invite_token, hash_invite_token, hash_password
from app.services.errors import ConflictError, ValidationError


def build_accept_url(raw_token: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/accept-invite?token={raw_token}"


def create_invitation(db: Session, *, email: str, invited_by: User) -> tuple[Invitation, str]:
    """Issue a member invitation. Returns ``(invitation, raw_token)``.

    The raw token is returned to the caller exactly once (for the accept link)
    and is never persisted — only its hash is stored. Any invitation for the
    same email that is still pending is expired now, so only the newest link
    works.
    """
    email = email.strip().lower()

    if db.scalar(select(User).where(User.email == email)) is not None:
        raise ConflictError("A user with that email already exists")

    now = datetime.now(UTC)
    stale = db.scalars(
        select(Invitation).where(
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > now,
        )
    )
    for old in stale:
        old.expires_at = now

    raw_token, token_hash = generate_invite_token()
    invitation = Invitation(
        email=email,
        role=Role.MEMBER,
        invited_by_id=invited_by.id,
        token_hash=token_hash,
        expires_at=now + timedelta(days=settings.invite_expiry_days),
    )
    db.add(invitation)
    db.flush()
    return invitation, raw_token


def accept_invitation(db: Session, *, token: str, full_name: str, password: str) -> User:
    """Validate the token and create the member account in one transaction.

    The invitation row is locked ``FOR UPDATE`` so two concurrent accepts of the
    same token cannot both create an account; the unique constraint on
    ``users.email`` is the final backstop.
    """
    invitation = db.scalar(
        select(Invitation)
        .where(Invitation.token_hash == hash_invite_token(token))
        .with_for_update()
    )
    if invitation is None:
        raise ValidationError("Invalid invitation token")

    now = datetime.now(UTC)
    if invitation.accepted_at is not None:
        raise ValidationError("This invitation has already been used")
    if invitation.expires_at <= now:
        raise ValidationError("This invitation has expired")

    if db.scalar(select(User).where(User.email == invitation.email)) is not None:
        raise ConflictError("A user with that email already exists")

    user = User(
        email=invitation.email,
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
        role=invitation.role,
        is_active=True,
    )
    db.add(user)

    savepoint = db.begin_nested()
    try:
        db.flush()
        savepoint.commit()
    except IntegrityError as exc:  # lost a race on users.email
        savepoint.rollback()
        raise ConflictError("A user with that email already exists") from exc

    invitation.accepted_at = now
    invitation.accepted_user = user
    db.flush()
    return user
