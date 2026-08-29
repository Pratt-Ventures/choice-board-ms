"""branding image original size and compression metadata

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-08-09 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, None] = "i0j1k2l3m4n5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customerbrandingimage", sa.Column("original_file_name", sa.String(), nullable=True))
    op.add_column("customerbrandingimage", sa.Column("original_byte_size", sa.Integer(), nullable=True))
    op.add_column(
        "customerbrandingimage",
        sa.Column("was_compressed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("customerbrandingimage", "was_compressed", server_default=None)
    op.execute(
        "UPDATE customerbrandingimage SET original_file_name = file_name "
        "WHERE original_file_name IS NULL"
    )
    op.execute(
        "UPDATE customerbrandingimage SET original_byte_size = byte_size "
        "WHERE original_byte_size IS NULL"
    )

    op.add_column("projectbrandingimage", sa.Column("original_file_name", sa.String(), nullable=True))
    op.add_column("projectbrandingimage", sa.Column("original_byte_size", sa.Integer(), nullable=True))
    op.add_column(
        "projectbrandingimage",
        sa.Column("was_compressed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("projectbrandingimage", "was_compressed", server_default=None)
    op.execute(
        "UPDATE projectbrandingimage SET original_file_name = file_name "
        "WHERE original_file_name IS NULL"
    )
    op.execute(
        "UPDATE projectbrandingimage SET original_byte_size = byte_size "
        "WHERE original_byte_size IS NULL"
    )


def downgrade() -> None:
    op.drop_column("projectbrandingimage", "was_compressed")
    op.drop_column("projectbrandingimage", "original_byte_size")
    op.drop_column("projectbrandingimage", "original_file_name")
    op.drop_column("customerbrandingimage", "was_compressed")
    op.drop_column("customerbrandingimage", "original_byte_size")
    op.drop_column("customerbrandingimage", "original_file_name")
