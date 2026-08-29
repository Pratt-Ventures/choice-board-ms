"""add option/factor questions per group on customerproject

Revision ID: p7q8r9s0t1u2
Revises: c7e8f9a0b1d2
Create Date: 2026-08-19 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p7q8r9s0t1u2"
down_revision: Union[str, None] = "c7e8f9a0b1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customerproject",
        sa.Column(
            "option_questions_per_group",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
    )
    op.add_column(
        "customerproject",
        sa.Column(
            "factor_questions_per_group",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
    )
    op.alter_column("customerproject", "option_questions_per_group", server_default=None)
    op.alter_column("customerproject", "factor_questions_per_group", server_default=None)


def downgrade() -> None:
    op.drop_column("customerproject", "factor_questions_per_group")
    op.drop_column("customerproject", "option_questions_per_group")
