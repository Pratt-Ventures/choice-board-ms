"""add_project_vote_event_tables

Revision ID: b2c3d4e5f6a7
Revises: 1fa893e89191
Create Date: 2026-08-05 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '1fa893e89191'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sa.Enum('session', 'share', name='votesource').create(op.get_bind())
    sa.Enum('alternative', 'criteria', name='observationtype').create(op.get_bind())
    sa.Enum('winner', 'tie', 'unsure', 'skipped', name='observationresponse').create(op.get_bind())

    op.create_table(
        'projectvoteparticipant',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('share_id', sa.Integer(), nullable=True),
        sa.Column('share_access_id', sa.Integer(), nullable=True),
        sa.Column('participant_key', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('source', postgresql.ENUM('session', 'share', name='votesource', create_type=False), nullable=False),
        sa.Column('observation_count', sa.Integer(), nullable=False),
        sa.Column('is_complete', sa.Boolean(), nullable=False),
        sa.Column('last_activity_date', sa.DateTime(), nullable=True),
        sa.Column('create_date', sa.DateTime(), nullable=True),
        sa.Column('modify_date', sa.DateTime(), nullable=True),
        sa.Column('deleted_date', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'project_id', 'participant_key', name='uq_vote_participant_key'),
    )
    op.create_index(op.f('ix_projectvoteparticipant_customer_id'), 'projectvoteparticipant', ['customer_id'], unique=False)
    op.create_index(op.f('ix_projectvoteparticipant_project_id'), 'projectvoteparticipant', ['project_id'], unique=False)
    op.create_index(op.f('ix_projectvoteparticipant_user_id'), 'projectvoteparticipant', ['user_id'], unique=False)
    op.create_index(op.f('ix_projectvoteparticipant_share_id'), 'projectvoteparticipant', ['share_id'], unique=False)
    op.create_index(op.f('ix_projectvoteparticipant_participant_key'), 'projectvoteparticipant', ['participant_key'], unique=False)
    op.create_index(op.f('ix_projectvoteparticipant_email'), 'projectvoteparticipant', ['email'], unique=False)

    op.create_table(
        'projectvoteobservation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('participant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('share_id', sa.Integer(), nullable=True),
        sa.Column('observation_type', postgresql.ENUM('alternative', 'criteria', name='observationtype', create_type=False), nullable=False),
        sa.Column('criterion_id', sa.Integer(), nullable=True),
        sa.Column('item_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('response', postgresql.ENUM('winner', 'tie', 'unsure', 'skipped', name='observationresponse', create_type=False), nullable=False),
        sa.Column('winner_id', sa.Integer(), nullable=True),
        sa.Column('predicted_id', sa.Integer(), nullable=True),
        sa.Column('predicted_probability', sa.Float(), nullable=True),
        sa.Column('prediction_correct', sa.Boolean(), nullable=True),
        sa.Column('client_event_id', sa.String(), nullable=True),
        sa.Column('algorithm_version', sa.String(), nullable=False),
        sa.Column('extra_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('create_date', sa.DateTime(), nullable=True),
        sa.Column('modify_date', sa.DateTime(), nullable=True),
        sa.Column('deleted_date', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('participant_id', 'client_event_id', name='uq_vote_obs_client_event'),
    )
    op.create_index(op.f('ix_projectvoteobservation_customer_id'), 'projectvoteobservation', ['customer_id'], unique=False)
    op.create_index(op.f('ix_projectvoteobservation_project_id'), 'projectvoteobservation', ['project_id'], unique=False)
    op.create_index(op.f('ix_projectvoteobservation_participant_id'), 'projectvoteobservation', ['participant_id'], unique=False)
    op.create_index(op.f('ix_projectvoteobservation_user_id'), 'projectvoteobservation', ['user_id'], unique=False)
    op.create_index(op.f('ix_projectvoteobservation_share_id'), 'projectvoteobservation', ['share_id'], unique=False)
    op.create_index(op.f('ix_projectvoteobservation_client_event_id'), 'projectvoteobservation', ['client_event_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_projectvoteobservation_client_event_id'), table_name='projectvoteobservation')
    op.drop_index(op.f('ix_projectvoteobservation_share_id'), table_name='projectvoteobservation')
    op.drop_index(op.f('ix_projectvoteobservation_user_id'), table_name='projectvoteobservation')
    op.drop_index(op.f('ix_projectvoteobservation_participant_id'), table_name='projectvoteobservation')
    op.drop_index(op.f('ix_projectvoteobservation_project_id'), table_name='projectvoteobservation')
    op.drop_index(op.f('ix_projectvoteobservation_customer_id'), table_name='projectvoteobservation')
    op.drop_table('projectvoteobservation')

    op.drop_index(op.f('ix_projectvoteparticipant_email'), table_name='projectvoteparticipant')
    op.drop_index(op.f('ix_projectvoteparticipant_participant_key'), table_name='projectvoteparticipant')
    op.drop_index(op.f('ix_projectvoteparticipant_share_id'), table_name='projectvoteparticipant')
    op.drop_index(op.f('ix_projectvoteparticipant_user_id'), table_name='projectvoteparticipant')
    op.drop_index(op.f('ix_projectvoteparticipant_project_id'), table_name='projectvoteparticipant')
    op.drop_index(op.f('ix_projectvoteparticipant_customer_id'), table_name='projectvoteparticipant')
    op.drop_table('projectvoteparticipant')

    sa.Enum(name='observationresponse').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='observationtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='votesource').drop(op.get_bind(), checkfirst=True)
