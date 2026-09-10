"""Project visibility: who may see which projects.

Managers see the whole portfolio. Members see only projects they belong to.
Every project- and task-scoped endpoint routes its access check through here, so
"members only see their projects" is enforced in one place on the server.

Visibility is separate from archiving: an archived project is still visible to
its members (and managers), it is just excluded from the default list views.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import Role
from app.models import Project, ProjectMembership, User
from app.services.errors import NotFoundError


def is_manager(user: User) -> bool:
    return user.role == Role.MANAGER


def visible_project_ids(db: Session, user: User) -> set[uuid.UUID] | None:
    """Project ids the user may see, or ``None`` meaning "all" (managers).

    Returning ``None`` lets query builders skip an ``IN (...)`` clause entirely
    for managers instead of materialising every id.
    """
    if is_manager(user):
        return None
    return set(
        db.scalars(select(ProjectMembership.project_id).where(ProjectMembership.user_id == user.id))
    )


def can_see_project(db: Session, user: User, project: Project) -> bool:
    if is_manager(user):
        return True
    return (
        db.scalar(
            select(ProjectMembership.id).where(
                ProjectMembership.project_id == project.id,
                ProjectMembership.user_id == user.id,
            )
        )
        is not None
    )


def get_visible_project_or_404(db: Session, user: User, project_id: uuid.UUID) -> Project:
    """Load a project the user is allowed to see, else 404 (never 403 — we don't
    confirm the existence of projects a member has no access to)."""
    project = db.get(Project, project_id)
    if project is None or not can_see_project(db, user, project):
        raise NotFoundError("Project not found")
    return project
