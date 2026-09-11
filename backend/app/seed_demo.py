"""Rich demo data for a deployed instance.

Run once, after ``python -m app.seed`` has created the initial manager:

    python -m app.seed_demo

Builds tasks through the real services (not raw inserts), so every status
move, assignment, dependency and comment produces the same event-logged
history a real user's action would — the demo timelines are genuine, not
faked. The one exception is ``Task.completed_at``, which is backdated
afterwards so the 8-week completions chart has a trend to show; nothing else
is backdated.

Members are inserted directly (bypassing the invitation flow) since this is a
one-time operator script, not a user-facing action.

Safe to run more than once: it exits early if the marker project (key
``WEBAPP``) already exists.
"""

from __future__ import annotations

import os
import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.enums import Role, TaskPriority, TaskStatus
from app.models import Project, Task, User
from app.schemas.project import ProjectCreate
from app.schemas.task import TaskCreate
from app.security import hash_password
from app.services import assignments
from app.services import projects as project_service
from app.services import tasks as task_service

_PASSWORD = "password123"

_MEMBERS = [
    ("alice@example.com", "Alice Chen"),
    ("bob@example.com", "Bob Martinez"),
    ("carol@example.com", "Carol Singh"),
    ("dana@example.com", "Dana Okafor"),
    ("evan@example.com", "Evan Brooks"),
]

_PATHS: dict[TaskStatus, list[TaskStatus]] = {
    TaskStatus.BACKLOG: [],
    TaskStatus.IN_PROGRESS: [TaskStatus.IN_PROGRESS],
    TaskStatus.IN_REVIEW: [TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW],
    TaskStatus.DONE: [TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW, TaskStatus.DONE],
    TaskStatus.BLOCKED: [TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED],
}


def _today() -> date:
    return datetime.now(UTC).date()


def _due(offset: int | None) -> date | None:
    return None if offset is None else _today() + timedelta(days=offset)


def _get_manager(db: Session) -> User:
    email = os.getenv("INITIAL_MANAGER_EMAIL", "manager@example.com").strip().lower()
    manager = db.scalar(select(User).where(User.email == email))
    if manager is None:
        raise RuntimeError("Run `python -m app.seed` first to create the initial manager.")
    return manager


def _get_or_create_members(db: Session) -> dict[str, User]:
    out: dict[str, User] = {}
    for email, name in _MEMBERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name=name,
                hashed_password=hash_password(_PASSWORD),
                role=Role.MEMBER,
                is_active=True,
            )
            db.add(user)
            db.flush()
        out[email.split("@")[0]] = user
    return out


def _make_project(db: Session, *, key: str, name: str, description: str, owner: User) -> Project:
    return project_service.create_project(
        db, data=ProjectCreate(key=key, name=name, description=description, owner_id=owner.id)
    )


def _make_task(
    db: Session,
    *,
    project: Project,
    title: str,
    description: str,
    priority: TaskPriority,
    due_offset: int | None,
    actor: User,
) -> Task:
    data = TaskCreate(
        title=title, description=description, priority=priority, due_date=_due(due_offset)
    )
    return task_service.create_task(db, project=project, data=data, actor=actor)


def _advance(db: Session, task: Task, status: TaskStatus, actor: User) -> None:
    for step in _PATHS[status]:
        task_service.transition_task(db, task=task, to_status=step, actor=actor)


def _complete_backdated(db: Session, task: Task, days_ago: int) -> None:
    task.completed_at = datetime.now(UTC) - timedelta(days=days_ago, hours=random.randint(0, 20))
    db.flush()


def _assign(db: Session, task: Task, actor: User, *assignees: User) -> None:
    for user in assignees:
        assignments.assign(db, task=task, user_id=user.id, actor=actor)


def _comment(db: Session, task: Task, actor: User, body: str) -> None:
    task_service.add_comment(db, task=task, body=body, actor=actor)


def _seed_webapp(db: Session, manager: User, m: dict[str, User]) -> None:
    p = _make_project(
        db,
        key="WEBAPP",
        name="Website Revamp",
        description="Public marketing site redesign.",
        owner=manager,
    )
    project_service.add_member(db, project=p, user_id=m["alice"].id)
    project_service.add_member(db, project=p, user_id=m["bob"].id)
    project_service.add_member(db, project=p, user_id=m["carol"].id)

    design_system = _make_task(
        db, project=p, title="Set up design system", description="Tokens, type scale, components.",
        priority=TaskPriority.HIGH, due_offset=None, actor=manager,
    )
    _advance(db, design_system, TaskStatus.DONE, manager)
    _assign(db, design_system, manager, m["alice"])
    _complete_backdated(db, design_system, 35)

    hero = _make_task(
        db, project=p, title="Homepage hero redesign", description="New hero section per the design system.",
        priority=TaskPriority.HIGH, due_offset=2, actor=manager,
    )
    task_service.add_dependency(db, task=hero, depends_on_task_id=design_system.id, actor=manager)
    _advance(db, hero, TaskStatus.IN_REVIEW, manager)
    _assign(db, hero, manager, m["alice"], m["bob"])
    _comment(db, hero, manager, "Waiting on stakeholder sign-off before we ship this.")

    nav = _make_task(
        db, project=p, title="Mobile nav overhaul", description="Hamburger menu is unusable on small screens.",
        priority=TaskPriority.MEDIUM, due_offset=-3, actor=manager,
    )
    _advance(db, nav, TaskStatus.IN_PROGRESS, manager)
    _assign(db, nav, manager, m["bob"])

    checkout = _make_task(
        db, project=p, title="Checkout flow QA", description="Full regression pass before launch.",
        priority=TaskPriority.URGENT, due_offset=1, actor=manager,
    )
    _advance(db, checkout, TaskStatus.BLOCKED, manager)
    _assign(db, checkout, manager, m["carol"])
    _comment(db, checkout, m["carol"], "Blocked - the payment gateway sandbox is down.")

    _make_task(
        db, project=p, title="Newsletter signup widget", description="",
        priority=TaskPriority.LOW, due_offset=None, actor=manager,
    )

    seo = _make_task(
        db, project=p, title="SEO audit", description="Meta tags, sitemap, structured data.",
        priority=TaskPriority.MEDIUM, due_offset=None, actor=manager,
    )
    _advance(db, seo, TaskStatus.DONE, manager)
    _assign(db, seo, manager, m["carol"])
    _complete_backdated(db, seo, 10)

    a11y = _make_task(
        db, project=p, title="Accessibility pass", description="WCAG AA audit and fixes.",
        priority=TaskPriority.MEDIUM, due_offset=5, actor=manager,
    )
    _advance(db, a11y, TaskStatus.IN_PROGRESS, manager)
    _assign(db, a11y, manager, m["alice"])

    _make_task(
        db, project=p, title="Launch checklist doc", description="",
        priority=TaskPriority.LOW, due_offset=20, actor=manager,
    )


def _seed_mobile(db: Session, manager: User, m: dict[str, User]) -> None:
    p = _make_project(
        db, key="MOBILE", name="Mobile App Launch",
        description="First-party iOS/Android app.", owner=manager,
    )
    project_service.add_member(db, project=p, user_id=m["bob"].id)
    project_service.add_member(db, project=p, user_id=m["dana"].id)

    listing = _make_task(
        db, project=p, title="App store listing copy", description="",
        priority=TaskPriority.MEDIUM, due_offset=None, actor=manager,
    )
    _advance(db, listing, TaskStatus.DONE, manager)
    _assign(db, listing, manager, m["dana"])
    _complete_backdated(db, listing, 20)

    push = _make_task(
        db, project=p, title="Push notification service", description="APNs + FCM integration.",
        priority=TaskPriority.HIGH, due_offset=-1, actor=manager,
    )
    _advance(db, push, TaskStatus.IN_PROGRESS, manager)
    _assign(db, push, manager, m["bob"])

    onboarding = _make_task(
        db, project=p, title="Onboarding flow v2", description="",
        priority=TaskPriority.HIGH, due_offset=3, actor=manager,
    )
    task_service.add_dependency(db, task=onboarding, depends_on_task_id=push.id, actor=manager)
    _advance(db, onboarding, TaskStatus.IN_REVIEW, manager)
    _assign(db, onboarding, manager, m["dana"], m["bob"])

    _make_task(
        db, project=p, title="Crash reporting integration", description="",
        priority=TaskPriority.URGENT, due_offset=-5, actor=manager,
    )

    _make_task(
        db, project=p, title="Dark mode support", description="",
        priority=TaskPriority.LOW, due_offset=None, actor=manager,
    )

    beta = _make_task(
        db, project=p, title="Beta tester invite flow", description="",
        priority=TaskPriority.MEDIUM, due_offset=None, actor=manager,
    )
    _advance(db, beta, TaskStatus.DONE, manager)
    _assign(db, beta, manager, m["bob"])
    _complete_backdated(db, beta, 3)

    icon = _make_task(
        db, project=p, title="App icon refresh", description="",
        priority=TaskPriority.LOW, due_offset=7, actor=manager,
    )
    _advance(db, icon, TaskStatus.IN_REVIEW, manager)
    _assign(db, icon, manager, m["dana"])


def _seed_infra(db: Session, manager: User, m: dict[str, User]) -> None:
    p = _make_project(
        db, key="INFRA", name="Infra Migration",
        description="Move off the old hosting provider.", owner=manager,
    )
    project_service.add_member(db, project=p, user_id=m["carol"].id)
    project_service.add_member(db, project=p, user_id=m["evan"].id)

    migrate = _make_task(
        db, project=p, title="Migrate DB to managed Postgres", description="",
        priority=TaskPriority.URGENT, due_offset=4, actor=manager,
    )
    _advance(db, migrate, TaskStatus.IN_PROGRESS, manager)
    _assign(db, migrate, manager, m["carol"], m["evan"])

    staging = _make_task(
        db, project=p, title="Set up staging environment", description="",
        priority=TaskPriority.HIGH, due_offset=None, actor=manager,
    )
    _advance(db, staging, TaskStatus.DONE, manager)
    _assign(db, staging, manager, m["evan"])
    _complete_backdated(db, staging, 45)

    ci = _make_task(
        db, project=p, title="CI pipeline hardening", description="",
        priority=TaskPriority.MEDIUM, due_offset=6, actor=manager,
    )
    _advance(db, ci, TaskStatus.IN_REVIEW, manager)
    _assign(db, ci, manager, m["carol"])

    secrets = _make_task(
        db, project=p, title="Secrets rotation policy", description="",
        priority=TaskPriority.MEDIUM, due_offset=-2, actor=manager,
    )
    task_service.add_dependency(db, task=secrets, depends_on_task_id=migrate.id, actor=manager)
    _advance(db, secrets, TaskStatus.BLOCKED, manager)
    _assign(db, secrets, manager, m["evan"])

    _make_task(
        db, project=p, title="Cost monitoring dashboard", description="",
        priority=TaskPriority.LOW, due_offset=None, actor=manager,
    )

    load = _make_task(
        db, project=p, title="Load testing", description="",
        priority=TaskPriority.HIGH, due_offset=None, actor=manager,
    )
    _advance(db, load, TaskStatus.DONE, manager)
    _assign(db, load, manager, m["carol"])
    _complete_backdated(db, load, 15)

    _make_task(
        db, project=p, title="Disaster recovery runbook", description="",
        priority=TaskPriority.MEDIUM, due_offset=30, actor=manager,
    )


def _seed_crm(db: Session, manager: User, m: dict[str, User]) -> None:
    p = _make_project(
        db, key="CRM", name="Client Portal",
        description="Self-serve portal for retainer clients.", owner=manager,
    )
    project_service.add_member(db, project=p, user_id=m["alice"].id)
    project_service.add_member(db, project=p, user_id=m["dana"].id)

    sso = _make_task(
        db, project=p, title="Client auth SSO", description="",
        priority=TaskPriority.HIGH, due_offset=None, actor=manager,
    )
    _advance(db, sso, TaskStatus.DONE, manager)
    _assign(db, sso, manager, m["alice"])
    _complete_backdated(db, sso, 50)

    billing = _make_task(
        db, project=p, title="Billing sync", description="",
        priority=TaskPriority.HIGH, due_offset=None, actor=manager,
    )
    _advance(db, billing, TaskStatus.DONE, manager)
    _assign(db, billing, manager, m["dana"])
    _complete_backdated(db, billing, 25)

    ticket = _make_task(
        db, project=p, title="Support ticket widget", description="",
        priority=TaskPriority.MEDIUM, due_offset=10, actor=manager,
    )
    _advance(db, ticket, TaskStatus.IN_REVIEW, manager)
    _assign(db, ticket, manager, m["alice"])

    _make_task(
        db, project=p, title="Data export tool", description="",
        priority=TaskPriority.LOW, due_offset=None, actor=manager,
    )

    audit = _make_task(
        db, project=p, title="Audit log viewer", description="",
        priority=TaskPriority.MEDIUM, due_offset=8, actor=manager,
    )
    _advance(db, audit, TaskStatus.IN_PROGRESS, manager)
    _assign(db, audit, manager, m["dana"])

    cleanup = _make_task(
        db, project=p, title="Legacy migration cleanup", description="",
        priority=TaskPriority.LOW, due_offset=None, actor=manager,
    )
    _advance(db, cleanup, TaskStatus.DONE, manager)
    _assign(db, cleanup, manager, m["alice"])
    _complete_backdated(db, cleanup, 5)

    # Demonstrates archiving: hidden from default views, data intact.
    project_service.archive_project(db, project=p)


def run() -> None:
    with SessionLocal() as db:
        manager = _get_manager(db)
        if db.scalar(select(Project).where(Project.key == "WEBAPP")) is not None:
            print("Demo data already present - nothing to do.")
            return

        members = _get_or_create_members(db)
        db.flush()

        _seed_webapp(db, manager, members)
        _seed_mobile(db, manager, members)
        _seed_infra(db, manager, members)
        _seed_crm(db, manager, members)

        db.commit()
        print(
            f"Seeded 4 projects, {len(members)} members "
            f"(password {_PASSWORD!r} for all of them), and their tasks."
        )


if __name__ == "__main__":
    run()
