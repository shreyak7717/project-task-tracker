"""add task_events.seq ordering column

Revision ID: 215d3a10ef11
Revises: 737a6a4b87fb
Create Date: 2026-09-10 19:57:58.596892
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '215d3a10ef11'
down_revision: str | None = '737a6a4b87fb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "task_events",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
    )
    op.create_unique_constraint("uq_task_events_seq", "task_events", ["seq"])


def downgrade() -> None:
    op.drop_constraint("uq_task_events_seq", "task_events", type_="unique")
    op.drop_column("task_events", "seq")
