"""add user communication tables

Revision ID: c7e8f9a0b1d2
Revises: 5d013b882699
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e8f9a0b1d2"
down_revision: Union[str, None] = "5d013b882699"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _lifecycle_columns():
    return [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("acknowledge_date", sa.DateTime(), nullable=True),
        sa.Column("acknowledge_user_id", sa.Integer(), nullable=True),
        sa.Column("acknowledge_note", sa.String(), nullable=True),
        sa.Column("response_date", sa.DateTime(), nullable=True),
        sa.Column("response_user_id", sa.Integer(), nullable=True),
        sa.Column("response_note", sa.String(), nullable=True),
        sa.Column("resolution_date", sa.DateTime(), nullable=True),
        sa.Column("resolution_user_id", sa.Integer(), nullable=True),
        sa.Column("resolution_note", sa.String(), nullable=True),
        sa.Column("attachment_filename", sa.String(), nullable=True),
        sa.Column("attachment_content_type", sa.String(), nullable=True),
        sa.Column("attachment_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("create_date", sa.DateTime(), nullable=True),
        sa.Column("modify_date", sa.DateTime(), nullable=True),
        sa.Column("deleted_date", sa.DateTime(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "bugreport",
        *_lifecycle_columns(),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("what_happened", sa.String(), nullable=False),
        sa.Column("expected_happened", sa.String(), nullable=True),
        sa.Column("steps_to_reproduce", sa.String(), nullable=True),
        sa.Column("impact", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bugreport_customer_id"), "bugreport", ["customer_id"], unique=False)
    op.create_index(op.f("ix_bugreport_user_id"), "bugreport", ["user_id"], unique=False)
    op.create_index("ix_bugreport_user_create", "bugreport", ["user_id", "create_date"], unique=False)
    op.create_index("ix_bugreport_customer_create", "bugreport", ["customer_id", "create_date"], unique=False)
    op.create_index("ix_bugreport_deleted_create", "bugreport", ["deleted_date", "create_date"], unique=False)

    op.create_table(
        "suggestion",
        *_lifecycle_columns(),
        sa.Column("suggestion", sa.String(), nullable=False),
        sa.Column("accomplish_goal", sa.String(), nullable=True),
        sa.Column("product_area", sa.String(), nullable=True),
        sa.Column("importance", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_suggestion_customer_id"), "suggestion", ["customer_id"], unique=False)
    op.create_index(op.f("ix_suggestion_user_id"), "suggestion", ["user_id"], unique=False)
    op.create_index("ix_suggestion_user_create", "suggestion", ["user_id", "create_date"], unique=False)
    op.create_index("ix_suggestion_customer_create", "suggestion", ["customer_id", "create_date"], unique=False)
    op.create_index("ix_suggestion_deleted_create", "suggestion", ["deleted_date", "create_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_suggestion_deleted_create", table_name="suggestion")
    op.drop_index("ix_suggestion_customer_create", table_name="suggestion")
    op.drop_index("ix_suggestion_user_create", table_name="suggestion")
    op.drop_index(op.f("ix_suggestion_user_id"), table_name="suggestion")
    op.drop_index(op.f("ix_suggestion_customer_id"), table_name="suggestion")
    op.drop_table("suggestion")
    op.drop_index("ix_bugreport_deleted_create", table_name="bugreport")
    op.drop_index("ix_bugreport_customer_create", table_name="bugreport")
    op.drop_index("ix_bugreport_user_create", table_name="bugreport")
    op.drop_index(op.f("ix_bugreport_user_id"), table_name="bugreport")
    op.drop_index(op.f("ix_bugreport_customer_id"), table_name="bugreport")
    op.drop_table("bugreport")
