"""SQLAlchemy ORM models — the whole schema in one file.

Design notes:
- UUID primary keys everywhere (``sqlalchemy.Uuid``), so ids are safe to expose
  in URLs and generated client-side without a round trip.
- Timestamps are timezone-aware and default on the server (``func.now()``).
- Join tables (``ProjectMembership``, ``TaskAssignee``, ``TaskDependency``) are
  explicit models rather than ``secondary=`` tables because they carry their own
  columns and we write history rows when they change.
- ``TaskEvent`` is append-only. There is deliberately no update path for it
  anywhere in the codebase (see docs/decisions.md).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import Role, TaskEventType, TaskPriority, TaskStatus


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(String(20), nullable=False, default=Role.MEMBER)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    owned_projects: Mapped[list[Project]] = relationship(
        back_populates="owner", foreign_keys="Project.owner_id"
    )
    memberships: Mapped[list[ProjectMembership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    assignments: Mapped[list[TaskAssignee]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _uuid_pk()
    key: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="owned_projects", foreign_keys=[owner_id])
    memberships: Mapped[list[ProjectMembership]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[Task]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectMembership(Base):
    """Who is staffed on a project. Many-to-many between users and projects."""

    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_membership_project_user"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[TaskPriority] = mapped_column(
        String(20), nullable=False, default=TaskPriority.MEDIUM, index=True
    )
    status: Mapped[TaskStatus] = mapped_column(
        String(20), nullable=False, default=TaskStatus.BACKLOG, index=True
    )
    # When BLOCKED, the status to return to on unblock. Null otherwise.
    blocked_from_status: Mapped[TaskStatus | None] = mapped_column(String(20), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    # Set when the task enters DONE, cleared on reopen. Powers "completed this
    # week" and the 8-week completions chart without scanning the event log.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="tasks")
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    assignees: Mapped[list[TaskAssignee]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    # Rows where THIS task is blocked by another.
    dependencies: Mapped[list[TaskDependency]] = relationship(
        back_populates="task",
        foreign_keys="TaskDependency.task_id",
        cascade="all, delete-orphan",
    )
    events: Mapped[list[TaskEvent]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="TaskEvent.created_at"
    )


class TaskDependency(Base):
    """``task_id`` is blocked by ``depends_on_task_id`` (which must reach Done).

    Both tasks must belong to the same project — enforced in the application
    layer, not the database (a cross-table check is awkward in Postgres).
    """

    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_dependency_pair"),
        CheckConstraint("task_id <> depends_on_task_id", name="ck_dependency_not_self"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    task: Mapped[Task] = relationship(back_populates="dependencies", foreign_keys=[task_id])
    depends_on: Mapped[Task] = relationship(foreign_keys=[depends_on_task_id])


class TaskAssignee(Base):
    """Many-to-many between tasks and users. Only project members may appear."""

    __tablename__ = "task_assignees"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_assignee_task_user"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    task: Mapped[Task] = relationship(back_populates="assignees")
    user: Mapped[User] = relationship(back_populates="assignments")


class TaskEvent(Base):
    """Append-only timeline entry for a task.

    Covers creation, every field change (with old/new), assignment changes,
    dependency changes, and comments. Never updated or deleted — not by anyone.
    """

    __tablename__ = "task_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Null actor = system-generated (e.g. cascade unassignment on project removal).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event_type: Mapped[TaskEventType] = mapped_column(String(30), nullable=False)
    field: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    task: Mapped[Task] = relationship(back_populates="events")
    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])


class AlertDismissal(Base):
    """A user dismissing the overdue alert for one task.

    ``dismissed_due_date`` records the task's due date at dismissal time. The
    alert reappears when the task's current due date differs from this value.
    """

    __tablename__ = "alert_dismissals"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_dismissal_task_user"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dismissed_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
