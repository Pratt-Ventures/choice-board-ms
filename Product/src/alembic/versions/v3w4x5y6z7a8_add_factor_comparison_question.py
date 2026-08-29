"""add optional comparison_question to customerprojectfactors

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-08-21 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v3w4x5y6z7a8"
down_revision: Union[str, None] = "u2v3w4x5y6z7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customerprojectfactors",
        sa.Column("comparison_question", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customerprojectfactors", "comparison_question")
