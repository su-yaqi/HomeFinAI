"""Harden auth and category integrity

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-07-18 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op


revision = "d4e5f6a7b8c9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"),
    )

    # Preserve existing references while merging any duplicates created by races
    # before the database-level uniqueness rule existed.
    op.execute(
        """
        CREATE TEMP TABLE category_duplicate_map AS
        SELECT id AS duplicate_id, canonical_id
        FROM (
            SELECT
                id,
                first_value(id) OVER (
                    PARTITION BY owner_id, name
                    ORDER BY created_at NULLS LAST, id
                ) AS canonical_id,
                row_number() OVER (
                    PARTITION BY owner_id, name
                    ORDER BY created_at NULLS LAST, id
                ) AS row_number
            FROM category
        ) ranked
        WHERE row_number > 1
        """
    )
    op.execute(
        """
        UPDATE "transaction" AS transaction_row
        SET category_id = duplicate_map.canonical_id
        FROM category_duplicate_map AS duplicate_map
        WHERE transaction_row.category_id = duplicate_map.duplicate_id
        """
    )
    op.execute(
        """
        UPDATE category AS child
        SET parent_id = CASE
            WHEN child.id = duplicate_map.canonical_id THEN NULL
            ELSE duplicate_map.canonical_id
        END
        FROM category_duplicate_map AS duplicate_map
        WHERE child.parent_id = duplicate_map.duplicate_id
        """
    )
    op.execute(
        """
        DELETE FROM category
        USING category_duplicate_map
        WHERE category.id = category_duplicate_map.duplicate_id
        """
    )
    op.execute("UPDATE category SET parent_id = NULL WHERE parent_id = id")
    op.execute(
        """
        WITH RECURSIVE ancestors AS (
            SELECT id AS origin_id, parent_id, ARRAY[id] AS path, FALSE AS cycle
            FROM category
            UNION ALL
            SELECT
                ancestors.origin_id,
                parent.parent_id,
                ancestors.path || parent.id,
                parent.id = ANY(ancestors.path)
            FROM ancestors
            JOIN category AS parent ON parent.id = ancestors.parent_id
            WHERE NOT ancestors.cycle
        ),
        cyclic AS (
            SELECT DISTINCT origin_id FROM ancestors WHERE cycle
        )
        UPDATE category
        SET parent_id = NULL
        FROM cyclic
        WHERE category.id = cyclic.origin_id
        """
    )
    op.create_unique_constraint(
        "uq_category_owner_name", "category", ["owner_id", "name"]
    )
    op.execute(
        """
        UPDATE category
        SET color = '#64748b'
        WHERE color !~ '^#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$'
        """
    )
    op.create_check_constraint(
        "ck_category_color_hex",
        "category",
        "color ~ '^#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$'",
    )

    op.drop_constraint("apitoken_created_by_fkey", "apitoken", type_="foreignkey")
    op.create_foreign_key(
        "apitoken_created_by_fkey",
        "apitoken",
        "user",
        ["created_by"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_table(
        "apitokennonce",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_id", sa.Uuid(), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["token_id"], ["apitoken.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_id", "nonce", name="uq_apitokennonce_token_nonce"
        ),
    )
    op.create_index(
        op.f("ix_apitokennonce_token_id"),
        "apitokennonce",
        ["token_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_apitokennonce_token_id"), table_name="apitokennonce")
    op.drop_table("apitokennonce")
    op.drop_constraint("apitoken_created_by_fkey", "apitoken", type_="foreignkey")
    op.create_foreign_key(
        "apitoken_created_by_fkey",
        "apitoken",
        "user",
        ["created_by"],
        ["id"],
    )
    op.drop_constraint("uq_category_owner_name", "category", type_="unique")
    op.drop_constraint("ck_category_color_hex", "category", type_="check")
    op.drop_column("user", "auth_version")
