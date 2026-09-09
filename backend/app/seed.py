"""Seed the database with an initial manager account.

    python -m app.seed

Idempotent: a second run detects the existing account and does nothing. This is
the bootstrap for the invitation chain — every other account is created by a
manager inviting someone. Session 6 grows this file into full demo data
(projects, tasks, history) for the deployed instance.

Credentials come from env vars, with local-dev defaults:
    INITIAL_MANAGER_EMAIL     (default manager@example.com)
    INITIAL_MANAGER_PASSWORD  (default manager1234 — a warning is printed)
    INITIAL_MANAGER_NAME      (default "Initial Manager")
"""

from __future__ import annotations

import os

from sqlalchemy import select

from app.db import SessionLocal
from app.enums import Role
from app.models import User
from app.security import hash_password

_DEFAULT_PASSWORD = "manager1234"


def create_initial_manager() -> None:
    email = os.getenv("INITIAL_MANAGER_EMAIL", "manager@example.com").strip().lower()
    password = os.getenv("INITIAL_MANAGER_PASSWORD", _DEFAULT_PASSWORD)
    name = os.getenv("INITIAL_MANAGER_NAME", "Initial Manager")

    if password == _DEFAULT_PASSWORD:
        print("WARNING: using the default manager password. Set INITIAL_MANAGER_PASSWORD.")

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)) is not None:
            print(f"Manager {email!r} already exists - nothing to do.")
            return
        db.add(
            User(
                email=email,
                full_name=name,
                hashed_password=hash_password(password),
                role=Role.MANAGER,
                is_active=True,
            )
        )
        db.commit()
        print(f"Created manager {email!r}.")


if __name__ == "__main__":
    create_initial_manager()
