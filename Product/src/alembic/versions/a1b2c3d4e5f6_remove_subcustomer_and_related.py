"""remove subcustomer concepts and app stripe / probe flags

Revision ID: a1b2c3d4e5f6
Revises: 13bfd4b363b7
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '13bfd4b363b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('subcustomerprobeevent')
    op.drop_table('subsubscribertransaction')
    op.drop_table('subcustomer')

    op.drop_column('customer', 'grace_period_hours')

    op.drop_column('apiaccessconfiguration', 'enable_probe')
    op.drop_column('apiaccessconfiguration', 'enable_dashboard')

    op.drop_index(op.f('ix_customerapplication_customer_stripe_hook'), table_name='customerapplication')
    op.drop_column('customerapplication', 'customer_stripe_hook')
    op.drop_column('customerapplication', 'customer_stripe_secret')


def downgrade() -> None:
    op.add_column('customerapplication', sa.Column('customer_stripe_secret', sa.String(), nullable=True))
    op.add_column('customerapplication', sa.Column('customer_stripe_hook', sa.String(), nullable=True))
    op.create_index(op.f('ix_customerapplication_customer_stripe_hook'), 'customerapplication', ['customer_stripe_hook'], unique=True)

    op.add_column('apiaccessconfiguration', sa.Column('enable_dashboard', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('apiaccessconfiguration', sa.Column('enable_probe', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('apiaccessconfiguration', 'enable_dashboard', server_default=None)
    op.alter_column('apiaccessconfiguration', 'enable_probe', server_default=None)

    op.add_column('customer', sa.Column('grace_period_hours', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('customer', 'grace_period_hours', server_default=None)

    op.create_table(
        'subcustomer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sub_customer_email', sa.String(), nullable=False),
        sa.Column('primary_customer_id', sa.Integer(), nullable=False),
        sa.Column('application_tag', sa.String(), nullable=True),
        sa.Column('sub_customer_account', sa.String(), nullable=True),
        sa.Column('sub_customer_name', sa.String(), nullable=False),
        sa.Column('sub_customer_phone', sa.String(), nullable=True),
        sa.Column('trial_activation_code', sa.String(), nullable=True),
        sa.Column('trial_expiration_date', sa.DateTime(), nullable=True),
        sa.Column('service_expiration_date', sa.DateTime(), nullable=True),
        sa.Column('sandbox_count', sa.Integer(), nullable=True),
        sa.Column('create_date', sa.DateTime(), nullable=True),
        sa.Column('modify_date', sa.DateTime(), nullable=True),
        sa.Column('deleted_date', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_subcustomer_sub_customer_account'), 'subcustomer', ['sub_customer_account'], unique=True)
    op.create_index(op.f('ix_subcustomer_sub_customer_email'), 'subcustomer', ['sub_customer_email'], unique=False)
    op.create_index(op.f('ix_subcustomer_primary_customer_id'), 'subcustomer', ['primary_customer_id'], unique=False)

    op.create_table(
        'subsubscribertransaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('financial_event_row_id', sa.Integer(), nullable=True),
        sa.Column('financial_event_source', sa.String(), nullable=True),
        sa.Column('financial_event_type', sa.String(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('financial_transaction_amount', sa.Float(), nullable=False),
        sa.Column('financial_transaction_currency', sa.String(), nullable=True),
        sa.Column('financial_discount_amount', sa.Float(), nullable=False),
        sa.Column('csr_user_id', sa.Integer(), nullable=True),
        sa.Column('csr_user_name', sa.String(), nullable=True),
        sa.Column('csr_notes', sa.String(), nullable=True),
        sa.Column('sandbox_mismatch', sa.Boolean(), nullable=True),
        sa.Column('livemode_flag', sa.Boolean(), nullable=False),
        sa.Column('transaction_type', sa.String(), nullable=False),
        sa.Column('transaction_units', sa.String(), nullable=False),
        sa.Column('transaction_month_count', sa.Integer(), nullable=False),
        sa.Column('transaction_day_count', sa.Integer(), nullable=False),
        sa.Column('transaction_trial_days_count', sa.Integer(), nullable=False),
        sa.Column('transaction_description', sa.String(), nullable=True),
        sa.Column('sub_customer_id', sa.Integer(), nullable=True),
        sa.Column('primary_customer_id', sa.Integer(), nullable=True),
        sa.Column('sub_customer_email', sa.String(), nullable=True),
        sa.Column('application_tag', sa.String(), nullable=True),
        sa.Column('transaction_date', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_subsubscribertransaction_sub_customer_id'), 'subsubscribertransaction', ['sub_customer_id'], unique=False)
    op.create_index(op.f('ix_subsubscribertransaction_primary_customer_id'), 'subsubscribertransaction', ['primary_customer_id'], unique=False)

    op.create_table(
        'subcustomerprobeevent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('primary_customer_id', sa.Integer(), nullable=True),
        sa.Column('application_tag', sa.String(), nullable=True),
        sa.Column('sub_customer_id', sa.Integer(), nullable=True),
        sa.Column('sub_customer_email', sa.String(), nullable=False),
        sa.Column('application_found', sa.Boolean(), nullable=False),
        sa.Column('application_active', sa.Boolean(), nullable=False),
        sa.Column('account_found', sa.Boolean(), nullable=False),
        sa.Column('account_deleted', sa.Boolean(), nullable=False),
        sa.Column('account_active', sa.Boolean(), nullable=False),
        sa.Column('grace_period_active', sa.Boolean(), nullable=False),
        sa.Column('service_expiration_date', sa.DateTime(), nullable=True),
        sa.Column('months_remaining', sa.Integer(), nullable=True),
        sa.Column('days_remaining', sa.Integer(), nullable=True),
        sa.Column('sandbox_count', sa.Integer(), nullable=True),
        sa.Column('event_date', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_subcustomerprobeevent_sub_customer_email'), 'subcustomerprobeevent', ['sub_customer_email'], unique=False)
    op.create_index(op.f('ix_subcustomerprobeevent_sub_customer_id'), 'subcustomerprobeevent', ['sub_customer_id'], unique=False)
