"""add ai connector tables

Revision ID: 8e4b1c9d2f30
Revises: f6e7d8c9b0a1
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8e4b1c9d2f30"
down_revision: str | None = "f6e7d8c9b0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aiconnection",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.String(length=500), nullable=False),
        sa.Column("client_name", sa.String(length=255), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aiconnection_user_id", "aiconnection", ["user_id"])
    op.create_table(
        "aiauthorizationcode",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("redirect_uri", sa.String(length=1000), nullable=False),
        sa.Column("code_challenge", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["aiconnection.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aiauthorizationcode_code_hash", "aiauthorizationcode", ["code_hash"], unique=True)
    op.create_index("ix_aiauthorizationcode_connection_id", "aiauthorizationcode", ["connection_id"])
    op.create_table(
        "airefreshtoken",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["aiconnection.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["replaced_by_id"], ["airefreshtoken.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_airefreshtoken_connection_id", "airefreshtoken", ["connection_id"])
    op.create_index("ix_airefreshtoken_family_id", "airefreshtoken", ["family_id"])
    op.create_index("ix_airefreshtoken_token_hash", "airefreshtoken", ["token_hash"], unique=True)
    op.create_table(
        "aioperation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["aiconnection.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", "tool_name", "idempotency_key", name="uq_aioperation_connection_tool_key"),
    )
    op.create_index("ix_aioperation_connection_id", "aioperation", ["connection_id"])

    op.execute(sa.text("UPDATE apitoken SET is_active = false WHERE is_active = true"))


def downgrade() -> None:
    op.drop_index("ix_aioperation_connection_id", table_name="aioperation")
    op.drop_table("aioperation")
    op.drop_index("ix_airefreshtoken_token_hash", table_name="airefreshtoken")
    op.drop_index("ix_airefreshtoken_family_id", table_name="airefreshtoken")
    op.drop_index("ix_airefreshtoken_connection_id", table_name="airefreshtoken")
    op.drop_table("airefreshtoken")
    op.drop_index("ix_aiauthorizationcode_connection_id", table_name="aiauthorizationcode")
    op.drop_index("ix_aiauthorizationcode_code_hash", table_name="aiauthorizationcode")
    op.drop_table("aiauthorizationcode")
    op.drop_index("ix_aiconnection_user_id", table_name="aiconnection")
    op.drop_table("aiconnection")
