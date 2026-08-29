"""store applicationlogevent.details_json as jsonb

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-08-15 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n5o6p7q8r9s0"
down_revision: Union[str, None] = "m4n5o6p7q8r9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "applicationlogevent",
        "details_json",
        existing_type=sa.VARCHAR(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using=(
            "CASE WHEN details_json IS NULL OR btrim(details_json) = '' "
            "THEN NULL ELSE details_json::jsonb END"
        ),
        existing_nullable=True,
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "applicationlogevent",
        "details_json",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.VARCHAR(),
        postgresql_using="details_json::text",
        existing_nullable=True,
        nullable=True,
    )
