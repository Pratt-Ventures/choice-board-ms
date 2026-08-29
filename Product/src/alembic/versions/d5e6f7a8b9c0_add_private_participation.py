"""add private_participation to customerproject

Revision ID: d5e6f7a8b9c0
Revises: 40828fe74b43
Create Date: 2026-08-07 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "40828fe74b43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customerproject",
        sa.Column(
            "private_participation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("customerproject", "private_participation", server_default=None)


def downgrade() -> None:
    op.drop_column("customerproject", "private_participation")
