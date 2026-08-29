"""add compare_prompt to alternatives and factors

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
Create Date: 2026-08-21 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w4x5y6z7a8b9"
down_revision: Union[str, None] = "v3w4x5y6z7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customerprojectalternatives", sa.Column("compare_prompt", sa.String(), nullable=True))
    op.add_column("customerprojectfactors", sa.Column("compare_prompt", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("customerprojectfactors", "compare_prompt")
    op.drop_column("customerprojectalternatives", "compare_prompt")
