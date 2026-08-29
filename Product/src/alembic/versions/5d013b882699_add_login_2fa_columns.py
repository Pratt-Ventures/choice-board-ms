"""add login 2fa columns

Revision ID: 5d013b882699
Revises: 4c902a771588
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5d013b882699"
down_revision: Union[str, None] = "4c902a771588"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("use_2fa", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("user", "use_2fa", server_default=None)
    op.add_column(
        "customer",
        sa.Column("use_2fa", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("customer", "use_2fa", server_default=None)
    op.add_column("userpasswords", sa.Column("last_2fa_hash", sa.String(), nullable=True))
    op.add_column("userpasswords", sa.Column("last_2fa_issued_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("userpasswords", "last_2fa_issued_at")
    op.drop_column("userpasswords", "last_2fa_hash")
    op.drop_column("customer", "use_2fa")
    op.drop_column("user", "use_2fa")
