"""external_api_event_generalization

Generalize the webhook event table for the pvf framework:
  - web_hook_type: hardcoded webhooktype PG enum -> varchar (application-registered types)
  - drop predecessor-product residue columns (probe_result, module_count_*)
  - add payload_params_json (JSONB) carried to the application's payload builder

Revision ID: 4c902a771588
Revises: 48d6f596a5a5
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '4c902a771588'
down_revision: Union[str, None] = '48d6f596a5a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'apiwebinvocationevent', 'web_hook_type',
        existing_type=sa.Enum('dummy_value', name='webhooktype'),
        type_=sa.String(length=80),
        existing_nullable=True,
        postgresql_using='web_hook_type::varchar(80)',
    )
    op.execute('DROP TYPE IF EXISTS webhooktype')

    op.drop_column('apiwebinvocationevent', 'probe_result')
    op.drop_column('apiwebinvocationevent', 'module_count_requested')
    op.drop_column('apiwebinvocationevent', 'module_count_completed')
    op.add_column('apiwebinvocationevent', sa.Column('payload_params_json', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('apiwebinvocationevent', 'payload_params_json')
    op.add_column('apiwebinvocationevent', sa.Column('module_count_completed', sa.Integer, nullable=True))
    op.add_column('apiwebinvocationevent', sa.Column('module_count_requested', sa.Integer, nullable=True))
    op.add_column('apiwebinvocationevent', sa.Column('probe_result', sa.Boolean, nullable=True))
    op.execute("CREATE TYPE webhooktype AS ENUM ('dummy_value')")
    op.alter_column(
        'apiwebinvocationevent', 'web_hook_type',
        existing_type=sa.String(length=80),
        type_=sa.Enum('dummy_value', name='webhooktype'),
        existing_nullable=True,
        postgresql_using='web_hook_type::webhooktype',
    )
