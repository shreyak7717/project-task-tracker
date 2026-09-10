"""Project and project-membership endpoints.

Manager-only: create, update, archive/restore, add/remove members.
Manager-or-member: list (visibility-filtered), get, list members.
A member requesting a project they are not on gets 404, not 403.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.deps import CurrentUser, DbSession, ManagerUser
from app.models import Project
from app.schemas.project import ProjectCreate, ProjectMemberOut, ProjectOut, ProjectUpdate
from app.services import projects as project_service
from app.services.visibility import get_visible_project_or_404

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_or_404(db: DbSession, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: DbSession, manager: ManagerUser) -> Project:
    project = project_service.create_project(db, data=body)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: DbSession, user: CurrentUser, include_archived: bool = Query(False)
) -> list[Project]:
    return project_service.list_visible_projects(db, user=user, include_archived=include_archived)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Project:
    return get_visible_project_or_404(db, user, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, db: DbSession, manager: ManagerUser
) -> Project:
    project = _get_or_404(db, project_id)
    project_service.update_project(db, project=project, data=body)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(project_id: uuid.UUID, db: DbSession, manager: ManagerUser) -> Project:
    project = _get_or_404(db, project_id)
    project_service.archive_project(db, project=project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/restore", response_model=ProjectOut)
def restore_project(project_id: uuid.UUID, db: DbSession, manager: ManagerUser) -> Project:
    project = _get_or_404(db, project_id)
    project_service.restore_project(db, project=project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
def list_members(project_id: uuid.UUID, db: DbSession, user: CurrentUser):
    project = get_visible_project_or_404(db, user, project_id)
    return project_service.list_members(db, project=project)


@router.put(
    "/{project_id}/members/{user_id}",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_200_OK,
)
def add_member(project_id: uuid.UUID, user_id: uuid.UUID, db: DbSession, manager: ManagerUser):
    project = _get_or_404(db, project_id)
    membership = project_service.add_member(db, project=project, user_id=user_id)
    db.commit()
    db.refresh(membership)
    return membership


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remove_member(project_id: uuid.UUID, user_id: uuid.UUID, db: DbSession, manager: ManagerUser):
    project = _get_or_404(db, project_id)
    project_service.remove_member(db, project=project, user_id=user_id)
    db.commit()
