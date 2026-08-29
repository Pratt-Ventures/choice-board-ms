"""add customer and project branding image tables

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-08-09 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i0j1k2l3m4n5"
down_revision: Union[str, None] = "h9i0j1k2l3m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customerbrandingimage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=True),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("create_date", sa.DateTime(), nullable=True),
        sa.Column("modify_date", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", name="uq_customerbrandingimage_customer_id"),
    )
    op.create_index(
        op.f("ix_customerbrandingimage_customer_id"),
        "customerbrandingimage",
        ["customer_id"],
        unique=False,
    )

    op.create_table(
        "projectbrandingimage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=True),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("create_date", sa.DateTime(), nullable=True),
        sa.Column("modify_date", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_projectbrandingimage_project_id"),
    )
    op.create_index(
        op.f("ix_projectbrandingimage_customer_id"),
        "projectbrandingimage",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_projectbrandingimage_project_id"),
        "projectbrandingimage",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_projectbrandingimage_project_id"), table_name="projectbrandingimage")
    op.drop_index(op.f("ix_projectbrandingimage_customer_id"), table_name="projectbrandingimage")
    op.drop_table("projectbrandingimage")
    op.drop_index(op.f("ix_customerbrandingimage_customer_id"), table_name="customerbrandingimage")
    op.drop_table("customerbrandingimage")
