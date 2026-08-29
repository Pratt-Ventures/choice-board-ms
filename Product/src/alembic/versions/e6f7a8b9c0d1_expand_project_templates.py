"""expand customerfactortemplates for project/option/factor scopes

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-08-07 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customerfactortemplates",
        sa.Column("option_template_entries", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "customerfactortemplates",
        sa.Column("use_with_projects", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "customerfactortemplates",
        sa.Column("use_with_options", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "customerfactortemplates",
        sa.Column("use_with_factors", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "customerfactortemplates",
        sa.Column("project_exclusive_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "customerfactortemplates",
        sa.Column("private_participation", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("customerfactortemplates", "use_with_projects", server_default=None)
    op.alter_column("customerfactortemplates", "use_with_options", server_default=None)
    op.alter_column("customerfactortemplates", "use_with_factors", server_default=None)
    op.alter_column("customerfactortemplates", "project_exclusive_mode", server_default=None)
    op.alter_column("customerfactortemplates", "private_participation", server_default=None)


def downgrade() -> None:
    op.drop_column("customerfactortemplates", "private_participation")
    op.drop_column("customerfactortemplates", "project_exclusive_mode")
    op.drop_column("customerfactortemplates", "use_with_factors")
    op.drop_column("customerfactortemplates", "use_with_options")
    op.drop_column("customerfactortemplates", "use_with_projects")
    op.drop_column("customerfactortemplates", "option_template_entries")
