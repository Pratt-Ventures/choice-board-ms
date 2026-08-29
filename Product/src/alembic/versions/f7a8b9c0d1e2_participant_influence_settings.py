"""add participant influence settings on customerproject

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-08-08 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customerproject",
        sa.Column(
            "participant_influence_mode",
            sa.String(),
            nullable=False,
            server_default="comparisons",
        ),
    )
    op.add_column(
        "customerproject",
        sa.Column(
            "participant_influence_min_comparisons",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    op.alter_column("customerproject", "participant_influence_mode", server_default=None)
    op.alter_column("customerproject", "participant_influence_min_comparisons", server_default=None)


def downgrade() -> None:
    op.drop_column("customerproject", "participant_influence_min_comparisons")
    op.drop_column("customerproject", "participant_influence_mode")
