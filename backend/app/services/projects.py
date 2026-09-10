"""Project lifecycle and membership.

Managers own all of this (enforced at the router). Visibility filtering for the
list/get paths lives in app.services.visibility.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Project, ProjectMembership, User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.visibility import visible_project_ids


def _require_active_user(db: Session, user_id: uuid.UUID, label: str) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise ValidationError(f"{label} must be an existing active user")
    return user


def _ensure_member(db: Session, project: Project, user_id: uuid.UUID) -> ProjectMembership:
    existing = db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project.id,
            ProjectMembership.user_id == user_id,
        )
    )
    if existing is not None:
        return existing
    membership = ProjectMembership(project_id=project.id, user_id=user_id)
    db.add(membership)
    db.flush()
    return membership


def create_project(db: Session, *, data: ProjectCreate) -> Project:
    if db.scalar(select(Project.id).where(Project.key == data.key)) is not None:
        raise ConflictError(f"Project key {data.key!r} is already taken")
    owner = _require_active_user(db, data.owner_id, "Owner")

    project = Project(
        key=data.key,
        name=data.name,
        description=data.description,
        owner_id=owner.id,
    )
    db.add(project)
    db.flush()
    _ensure_member(db, project, owner.id)  # the owner is always on the project
    return project


def update_project(db: Session, *, project: Project, data: ProjectUpdate) -> Project:
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.owner_id is not None and data.owner_id != project.owner_id:
        new_owner = _require_active_user(db, data.owner_id, "Owner")
        project.owner_id = new_owner.id
        _ensure_member(db, project, new_owner.id)
    db.flush()
    return project


def archive_project(db: Session, *, project: Project) -> Project:
    project.is_archived = True
    db.flush()
    return project


def restore_project(db: Session, *, project: Project) -> Project:
    project.is_archived = False
    db.flush()
    return project


def list_visible_projects(
    db: Session, *, user: User, include_archived: bool = False
) -> list[Project]:
    stmt = select(Project).options(selectinload(Project.owner)).order_by(Project.key)
    ids = visible_project_ids(db, user)
    if ids is not None:
        if not ids:
            return []
        stmt = stmt.where(Project.id.in_(ids))
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    return list(db.scalars(stmt))


def list_members(db: Session, *, project: Project) -> list[ProjectMembership]:
    return list(
        db.scalars(
            select(ProjectMembership)
            .options(selectinload(ProjectMembership.user))
            .join(User, ProjectMembership.user_id == User.id)
            .where(ProjectMembership.project_id == project.id)
            .order_by(User.full_name)
        )
    )


def add_member(db: Session, *, project: Project, user_id: uuid.UUID) -> ProjectMembership:
    _require_active_user(db, user_id, "User")
    return _ensure_member(db, project, user_id)


def remove_member(db: Session, *, project: Project, user_id: uuid.UUID) -> None:
    if user_id == project.owner_id:
        raise ValidationError("Cannot remove the project owner; change the owner first")
    membership = db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project.id,
            ProjectMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise NotFoundError("User is not a member of this project")
    db.delete(membership)
    # Session 4: also unassign this user from every task in this project.
    db.flush()
