"""customer AI credentials and multiple AI voters

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
Create Date: 2026-08-21 12:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "t1u2v3w4x5y6"
down_revision: Union[str, None] = "s0t1u2v3w4x5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customer", sa.Column("ai_provider", sa.String(), nullable=True))
    op.add_column("customer", sa.Column("ai_model", sa.String(), nullable=True))
    op.add_column("customer", sa.Column("ai_api_key", sa.String(), nullable=True))
    op.add_column(
        "projectvoteparticipant",
        sa.Column("is_ai", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("projectvoteparticipant", sa.Column("ai_model", sa.String(), nullable=True))
    op.execute("UPDATE projectvoteparticipant SET is_ai = true WHERE source = 'ai'")
    op.alter_column("projectvoteparticipant", "is_ai", server_default=None)
    op.add_column(
        "aiagentjob",
        sa.Column("model_key", sa.String(), nullable=False, server_default="__default__"),
    )
    op.create_index(op.f("ix_aiagentjob_model_key"), "aiagentjob", ["model_key"], unique=False)
    op.alter_column("aiagentjob", "model_key", server_default=None)
    op.add_column(
        "customerproject",
        sa.Column(
            "ai_voter_models",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("customerproject", "ai_voter_models", server_default=None)


def downgrade() -> None:
    op.drop_column("customerproject", "ai_voter_models")
    op.drop_index(op.f("ix_aiagentjob_model_key"), table_name="aiagentjob")
    op.drop_column("aiagentjob", "model_key")
    op.drop_column("projectvoteparticipant", "ai_model")
    op.drop_column("projectvoteparticipant", "is_ai")
    op.drop_column("customer", "ai_api_key")
    op.drop_column("customer", "ai_model")
    op.drop_column("customer", "ai_provider")
