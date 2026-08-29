"""store emailactivitylog.email_params_json as jsonb

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-08-15 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, None] = "l3m4n5o6p7q8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "emailactivitylog",
        "email_params_json",
        existing_type=sa.VARCHAR(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using=(
            "CASE WHEN email_params_json IS NULL OR btrim(email_params_json) = '' "
            "THEN '{}'::jsonb ELSE email_params_json::jsonb END"
        ),
        existing_nullable=True,
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "emailactivitylog",
        "email_params_json",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.VARCHAR(),
        postgresql_using="email_params_json::text",
        existing_nullable=False,
        nullable=True,
    )
