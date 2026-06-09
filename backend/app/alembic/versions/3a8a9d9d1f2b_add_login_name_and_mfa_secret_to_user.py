"""Add login_name and mfa_secret to user

Revision ID: 3a8a9d9d1f2b
Revises: fe56fa70289e
Create Date: 2026-05-28 23:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3a8a9d9d1f2b"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("login_name", sa.String(length=100), nullable=True))
    op.add_column("user", sa.Column("mfa_secret", sa.String(length=255), nullable=True))

    op.execute(
        """
        UPDATE "user"
        SET login_name = split_part(email, '@', 1)
        WHERE login_name IS NULL
        """
    )

    op.alter_column("user", "login_name", existing_type=sa.String(length=100), nullable=False)
    op.create_index(op.f("ix_user_login_name"), "user", ["login_name"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_user_login_name"), table_name="user")
    op.drop_column("user", "mfa_secret")
    op.drop_column("user", "login_name")
