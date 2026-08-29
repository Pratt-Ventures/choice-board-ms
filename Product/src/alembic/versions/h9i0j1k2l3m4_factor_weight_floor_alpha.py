"""add factor_weight_floor_alpha on customerproject

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-08-08 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h9i0j1k2l3m4"
down_revision: Union[str, None] = "g8h9i0j1k2l3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customerproject",
        sa.Column(
            "factor_weight_floor_alpha",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
    )
    # Keep default for new ORM rows; drop server default so the app owns the value.
    op.alter_column("customerproject", "factor_weight_floor_alpha", server_default=None)


def downgrade() -> None:
    op.drop_column("customerproject", "factor_weight_floor_alpha")
