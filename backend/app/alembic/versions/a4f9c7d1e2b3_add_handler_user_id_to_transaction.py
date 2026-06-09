"""Add handler_user_id to transaction

Revision ID: a4f9c7d1e2b3
Revises: 7b3f6c2d4e5f
Create Date: 2026-05-29 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a4f9c7d1e2b3"
down_revision = "7b3f6c2d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "transaction",
        sa.Column("handler_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute('UPDATE "transaction" SET handler_user_id = owner_id WHERE handler_user_id IS NULL')
    op.create_foreign_key(
        "fk_transaction_handler_user_id_user",
        "transaction",
        "user",
        ["handler_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_transaction_handler_user_id_user", "transaction", type_="foreignkey"
    )
    op.drop_column("transaction", "handler_user_id")
