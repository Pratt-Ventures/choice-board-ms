"""add compare prompt reword jobs table

Revision ID: x5y6z7a8b9c0
Revises: w4x5y6z7a8b9
Create Date: 2026-08-21 20:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "x5y6z7a8b9c0"
down_revision: Union[str, None] = "w4x5y6z7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comparepromptjob",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("error_summary", sa.String(), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("create_date", sa.DateTime(), nullable=True),
        sa.Column("modify_date", sa.DateTime(), nullable=True),
        sa.Column("started_date", sa.DateTime(), nullable=True),
        sa.Column("completed_date", sa.DateTime(), nullable=True),
        sa.Column("deleted_date", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comparepromptjob_customer_id"), "comparepromptjob", ["customer_id"], unique=False)
    op.create_index(op.f("ix_comparepromptjob_project_id"), "comparepromptjob", ["project_id"], unique=False)
    op.create_index(op.f("ix_comparepromptjob_item_type"), "comparepromptjob", ["item_type"], unique=False)
    op.create_index(op.f("ix_comparepromptjob_item_id"), "comparepromptjob", ["item_id"], unique=False)
    op.create_index(op.f("ix_comparepromptjob_status"), "comparepromptjob", ["status"], unique=False)
    op.alter_column("comparepromptjob", "details_json", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_comparepromptjob_status"), table_name="comparepromptjob")
    op.drop_index(op.f("ix_comparepromptjob_item_id"), table_name="comparepromptjob")
    op.drop_index(op.f("ix_comparepromptjob_item_type"), table_name="comparepromptjob")
    op.drop_index(op.f("ix_comparepromptjob_project_id"), table_name="comparepromptjob")
    op.drop_index(op.f("ix_comparepromptjob_customer_id"), table_name="comparepromptjob")
    op.drop_table("comparepromptjob")
