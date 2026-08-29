"""share_type_to_varchar_add_share_actions

Convert ShareLink.shared_type from the hardcoded sharetype PG enum to varchar so the
framework can carry application-supplied share vocabularies, and add
ShareLink.share_actions (JSONB, actions possible on the share, backfilled from the
historical validity matrix). The share record keeping of actions actually used already
lives in sharelinkaccessed.access_operation (JSONB).

Revision ID: 48d6f596a5a5
Revises: n5o6p7q8r9s0
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '48d6f596a5a5'
down_revision: Union[str, None] = 'n5o6p7q8r9s0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# historical full-validity matrix (any operation was reachable for any share type)
_BACKFILL_ACTIONS = '["vote", "view", "report"]'


def upgrade() -> None:
    op.alter_column(
        'sharelink', 'shared_type',
        existing_type=sa.Enum('not_set', 'vote', 'vote_view', 'report', name='sharetype'),
        type_=sa.String(length=50),
        existing_nullable=False,
        postgresql_using='shared_type::varchar(50)',
    )
    op.execute('DROP TYPE IF EXISTS sharetype')

    op.add_column('sharelink', sa.Column('share_actions', JSONB, nullable=True))
    op.execute(f"UPDATE sharelink SET share_actions = '{_BACKFILL_ACTIONS}'::jsonb WHERE share_actions IS NULL")


def downgrade() -> None:
    op.drop_column('sharelink', 'share_actions')
    op.execute("CREATE TYPE sharetype AS ENUM ('not_set', 'vote', 'vote_view', 'report')")
    op.alter_column(
        'sharelink', 'shared_type',
        existing_type=sa.String(length=50),
        type_=sa.Enum('not_set', 'vote', 'vote_view', 'report', name='sharetype'),
        existing_nullable=False,
        postgresql_using='shared_type::sharetype',
    )
