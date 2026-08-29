"""add customer projects alternatives criteria templates

Revision ID: a998d73dda92
Revises: a1b2c3d4e5f6
Create Date: 2026-08-04 02:17:25.340734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a998d73dda92'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('customerfactortemplates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('enable_global_share', sa.Boolean(), nullable=False),
    sa.Column('factor_template_title', sa.String(), nullable=True),
    sa.Column('factor_template_description', sa.String(), nullable=True),
    sa.Column('factor_template_entries', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('disabled', sa.Boolean(), nullable=False),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('modify_date', sa.DateTime(), nullable=True),
    sa.Column('deleted_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customerfactortemplates_customer_id'), 'customerfactortemplates', ['customer_id'], unique=False)
    op.create_table('customerproject',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('project_tag', sa.String(), nullable=False),
    sa.Column('project_title', sa.String(), nullable=True),
    sa.Column('project_description', sa.String(), nullable=True),
    sa.Column('project_exclusive_mode', sa.Boolean(), nullable=False),
    sa.Column('project_created_by', sa.Integer(), nullable=False),
    sa.Column('project_criteria_template', sa.Integer(), nullable=False),
    sa.Column('disabled', sa.Boolean(), nullable=False),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('modify_date', sa.DateTime(), nullable=True),
    sa.Column('deleted_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customerproject_customer_id'), 'customerproject', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customerproject_project_created_by'), 'customerproject', ['project_created_by'], unique=False)
    op.create_index(op.f('ix_customerproject_project_tag'), 'customerproject', ['project_tag'], unique=False)
    op.create_table('customerprojectalternatives',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('alternative_title', sa.String(), nullable=True),
    sa.Column('alternative_description', sa.String(), nullable=True),
    sa.Column('disabled', sa.Boolean(), nullable=False),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('modify_date', sa.DateTime(), nullable=True),
    sa.Column('deleted_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customerprojectalternatives_customer_id'), 'customerprojectalternatives', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customerprojectalternatives_project_id'), 'customerprojectalternatives', ['project_id'], unique=False)
    op.create_table('customerprojectfactors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('factor_title', sa.String(), nullable=True),
    sa.Column('factor_description', sa.String(), nullable=True),
    sa.Column('factor_polarity_positive', sa.Boolean(), nullable=False),
    sa.Column('factor_polarity_note', sa.String(), nullable=True),
    sa.Column('disabled', sa.Boolean(), nullable=False),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('modify_date', sa.DateTime(), nullable=True),
    sa.Column('deleted_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customerprojectfactors_customer_id'), 'customerprojectfactors', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customerprojectfactors_project_id'), 'customerprojectfactors', ['project_id'], unique=False)
    op.drop_index('ix_customerapplication_application_tag', table_name='customerapplication')
    op.drop_index('ix_customerapplication_customer_id', table_name='customerapplication')
    op.drop_table('customerapplication')


def downgrade() -> None:
    op.create_table('customerapplication',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('customer_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('application_tag', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('application_description', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('disabled', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('create_date', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('modify_date', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('deleted_date', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name='customerapplication_pkey')
    )
    op.create_index('ix_customerapplication_customer_id', 'customerapplication', ['customer_id'], unique=False)
    op.create_index('ix_customerapplication_application_tag', 'customerapplication', ['application_tag'], unique=False)
    op.drop_index(op.f('ix_customerprojectfactors_project_id'), table_name='customerprojectfactors')
    op.drop_index(op.f('ix_customerprojectfactors_customer_id'), table_name='customerprojectfactors')
    op.drop_table('customerprojectfactors')
    op.drop_index(op.f('ix_customerprojectalternatives_project_id'), table_name='customerprojectalternatives')
    op.drop_index(op.f('ix_customerprojectalternatives_customer_id'), table_name='customerprojectalternatives')
    op.drop_table('customerprojectalternatives')
    op.drop_index(op.f('ix_customerproject_project_tag'), table_name='customerproject')
    op.drop_index(op.f('ix_customerproject_project_created_by'), table_name='customerproject')
    op.drop_index(op.f('ix_customerproject_customer_id'), table_name='customerproject')
    op.drop_table('customerproject')
    op.drop_index(op.f('ix_customerfactortemplates_customer_id'), table_name='customerfactortemplates')
    op.drop_table('customerfactortemplates')
