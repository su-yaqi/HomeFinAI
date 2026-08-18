"""add ai authorization decisions

Revision ID: 9f5c2a7e1d44
Revises: 8e4b1c9d2f30
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f5c2a7e1d44"
down_revision: str | None = "8e4b1c9d2f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aiauthorizationdecision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_jti", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_aiauthorizationdecision_request_jti",
        "aiauthorizationdecision",
        ["request_jti"],
        unique=True,
    )
    op.create_index(
        "ix_aiauthorizationdecision_user_id",
        "aiauthorizationdecision",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_aiauthorizationdecision_user_id",
        table_name="aiauthorizationdecision",
    )
    op.drop_index(
        "ix_aiauthorizationdecision_request_jti",
        table_name="aiauthorizationdecision",
    )
    op.drop_table("aiauthorizationdecision")
