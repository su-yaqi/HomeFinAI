"""Add transaction summary and detail

Revision ID: b2c3d4e5f6a7
Revises: c1a2b3d4e5f6
Create Date: 2026-06-01 14:45:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b2c3d4e5f6a7"
down_revision = "c1a2b3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("transaction", sa.Column("summary", sa.String(length=255), nullable=True))
    op.add_column("transaction", sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute('UPDATE "transaction" SET summary = description WHERE summary IS NULL AND description IS NOT NULL')


def downgrade():
    op.drop_column("transaction", "detail")
    op.drop_column("transaction", "summary")
