"""add ai agent jobs and votesource ai

Revision ID: s0t1u2v3w4x5
Revises: r9s0t1u2v3w4
Create Date: 2026-08-21 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from alembic_postgresql_enum import TableReference
from sqlalchemy.dialects import postgresql

revision: str = "s0t1u2v3w4x5"
down_revision: Union[str, None] = "r9s0t1u2v3w4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.sync_enum_values(
        enum_schema="public",
        enum_name="votesource",
        new_values=["session", "share", "ai"],
        affected_columns=[
            TableReference(table_schema="public", table_name="projectvoteparticipant", column_name="source"),
        ],
        enum_values_to_rename=[],
    )
    op.create_table(
        "aiagentjob",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("participant_id", sa.Integer(), nullable=True),
        sa.Column("pair_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skip_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("group_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("create_date", sa.DateTime(), nullable=True),
        sa.Column("modify_date", sa.DateTime(), nullable=True),
        sa.Column("started_date", sa.DateTime(), nullable=True),
        sa.Column("completed_date", sa.DateTime(), nullable=True),
        sa.Column("deleted_date", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_aiagentjob_customer_id"), "aiagentjob", ["customer_id"], unique=False)
    op.create_index(op.f("ix_aiagentjob_project_id"), "aiagentjob", ["project_id"], unique=False)
    op.create_index(op.f("ix_aiagentjob_job_type"), "aiagentjob", ["job_type"], unique=False)
    op.create_index(op.f("ix_aiagentjob_status"), "aiagentjob", ["status"], unique=False)
    op.create_index(op.f("ix_aiagentjob_participant_id"), "aiagentjob", ["participant_id"], unique=False)
    op.alter_column("aiagentjob", "pair_count", server_default=None)
    op.alter_column("aiagentjob", "skip_count", server_default=None)
    op.alter_column("aiagentjob", "group_count", server_default=None)
    op.alter_column("aiagentjob", "details_json", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_aiagentjob_participant_id"), table_name="aiagentjob")
    op.drop_index(op.f("ix_aiagentjob_status"), table_name="aiagentjob")
    op.drop_index(op.f("ix_aiagentjob_job_type"), table_name="aiagentjob")
    op.drop_index(op.f("ix_aiagentjob_project_id"), table_name="aiagentjob")
    op.drop_index(op.f("ix_aiagentjob_customer_id"), table_name="aiagentjob")
    op.drop_table("aiagentjob")
    op.sync_enum_values(
        enum_schema="public",
        enum_name="votesource",
        new_values=["session", "share"],
        affected_columns=[
            TableReference(table_schema="public", table_name="projectvoteparticipant", column_name="source"),
        ],
        enum_values_to_rename=[],
    )
