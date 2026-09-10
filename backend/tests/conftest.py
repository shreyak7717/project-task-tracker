"""Pytest fixtures.

Tests run against a real Postgres database (``<db>_test`` on the same server as
the dev database), not SQLite, so UUIDs, constraints, cascades and ``FOR UPDATE``
behave exactly as in production.

Isolation: each test gets a ``Session`` bound to a single connection inside an
outer transaction that is rolled back at the end. ``join_transaction_mode=
"create_savepoint"`` means the code under test can call ``commit()`` /
``begin_nested()`` freely — those land on savepoints and never touch the outer
transaction.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, get_db
from app.enums import Role, TaskPriority, TaskStatus
from app.main import app
from app.models import Invitation, Project, ProjectMembership, Task, User
from app.security import create_access_token, generate_invite_token, hash_password

_DEV_URL = make_url(settings.database_url)
TEST_URL = _DEV_URL.set(database=f"{_DEV_URL.database}_test")
ADMIN_URL = _DEV_URL.set(database="postgres")


@pytest.fixture(scope="session")
def _create_test_database() -> Iterator[None]:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        already = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"),
            {"n": TEST_URL.database},
        ).scalar()
        if not already:
            conn.execute(text(f'CREATE DATABASE "{TEST_URL.database}"'))
    admin.dispose()
    yield


@pytest.fixture(scope="session")
def engine(_create_test_database: None) -> Iterator[Engine]:
    eng = create_engine(TEST_URL, pool_pre_ping=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- data fixtures --------------------------------------------------------


def _make_user(db: Session, *, email: str, name: str, role: Role, active: bool = True) -> User:
    user = User(
        email=email,
        full_name=name,
        hashed_password=hash_password("password123"),
        role=role,
        is_active=active,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def manager(db: Session) -> User:
    return _make_user(db, email="manager@example.com", name="Meg Manager", role=Role.MANAGER)


@pytest.fixture
def member(db: Session) -> User:
    return _make_user(db, email="member@example.com", name="Mo Member", role=Role.MEMBER)


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def _factory(
        *, email: str, name: str = "Test User", role: Role = Role.MEMBER, active: bool = True
    ) -> User:
        return _make_user(db, email=email, name=name, role=role, active=active)

    return _factory


@pytest.fixture
def auth_headers() -> Callable[[User], dict[str, str]]:
    def _headers(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(str(user.id), user.role)}"}

    return _headers


@pytest.fixture
def make_invitation(db: Session, manager: User) -> Callable[..., tuple[Invitation, str]]:
    def _factory(
        *,
        email: str = "invitee@example.com",
        role: Role = Role.MEMBER,
        expires_in_days: float = 7,
        accepted: bool = False,
    ) -> tuple[Invitation, str]:
        raw_token, token_hash = generate_invite_token()
        now = datetime.now(UTC)
        invitation = Invitation(
            email=email.strip().lower(),
            role=role,
            invited_by_id=manager.id,
            token_hash=token_hash,
            expires_at=now + timedelta(days=expires_in_days),
            accepted_at=now if accepted else None,
        )
        db.add(invitation)
        db.flush()
        return invitation, raw_token

    return _factory


@pytest.fixture
def make_project(db: Session, manager: User) -> Callable[..., Project]:
    def _factory(
        *,
        key: str = "ACME",
        name: str = "Acme Engagement",
        owner: User | None = None,
        archived: bool = False,
        members: tuple[User, ...] = (),
    ) -> Project:
        owner = owner or manager
        project = Project(
            key=key, name=name, description="", owner_id=owner.id, is_archived=archived
        )
        db.add(project)
        db.flush()
        seen = {owner.id}
        db.add(ProjectMembership(project_id=project.id, user_id=owner.id))
        for extra in members:
            if extra.id not in seen:
                db.add(ProjectMembership(project_id=project.id, user_id=extra.id))
                seen.add(extra.id)
        db.flush()
        return project

    return _factory


@pytest.fixture
def make_task(
    db: Session, make_project: Callable[..., Project], manager: User
) -> Callable[..., Task]:
    def _factory(
        *,
        project: Project | None = None,
        title: str = "A task",
        status: TaskStatus = TaskStatus.BACKLOG,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date=None,
        created_by: User | None = None,
        blocked_from_status: TaskStatus | None = None,
    ) -> Task:
        project = project or make_project()
        task = Task(
            project_id=project.id,
            title=title,
            description="",
            status=status,
            priority=priority,
            due_date=due_date,
            blocked_from_status=blocked_from_status,
            created_by_id=(created_by or manager).id,
        )
        db.add(task)
        db.flush()
        return task

    return _factory
