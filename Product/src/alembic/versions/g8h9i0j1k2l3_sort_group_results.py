"""replace vote observations with sort group results; add pass settings

Revision ID: g8h9i0j1k2l3
Revises: f7a8b9c0d1e2
Create Date: 2026-08-08 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g8h9i0j1k2l3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customerproject",
        sa.Column("min_expected_passes", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "customerproject",
        sa.Column("max_recommended_passes", sa.Integer(), nullable=False, server_default="4"),
    )
    op.alter_column("customerproject", "min_expected_passes", server_default=None)
    op.alter_column("customerproject", "max_recommended_passes", server_default=None)

    op.add_column(
        "projectvoteparticipant",
        sa.Column("group_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "projectvoteparticipant",
        sa.Column("comparison_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # Best-effort copy legacy observation_count into comparison_count before drop
    op.execute(
        "UPDATE projectvoteparticipant SET comparison_count = COALESCE(observation_count, 0)"
    )
    op.drop_column("projectvoteparticipant", "observation_count")
    op.alter_column("projectvoteparticipant", "group_count", server_default=None)
    op.alter_column("projectvoteparticipant", "comparison_count", server_default=None)

    op.drop_table("projectvoteobservation")

    op.create_table(
        "projectvotegroupresult",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("share_id", sa.Integer(), nullable=True),
        sa.Column("group_type", sa.String(), nullable=False),
        sa.Column("criterion_id", sa.Integer(), nullable=True),
        sa.Column("sort_algorithm", sa.String(), nullable=False),
        sa.Column("pass_index", sa.Integer(), nullable=False),
        sa.Column("item_ids_initial", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rank_order", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pairings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("comparison_count", sa.Integer(), nullable=False),
        sa.Column("client_group_id", sa.String(), nullable=False),
        sa.Column("algorithm_version", sa.String(), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(), nullable=True),
        sa.Column("create_date", sa.DateTime(), nullable=True),
        sa.Column("modify_date", sa.DateTime(), nullable=True),
        sa.Column("deleted_date", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("participant_id", "client_group_id", name="uq_vote_group_client_id"),
    )
    op.create_index(
        op.f("ix_projectvotegroupresult_customer_id"),
        "projectvotegroupresult",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_projectvotegroupresult_project_id"),
        "projectvotegroupresult",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_projectvotegroupresult_participant_id"),
        "projectvotegroupresult",
        ["participant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_projectvotegroupresult_user_id"),
        "projectvotegroupresult",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_projectvotegroupresult_share_id"),
        "projectvotegroupresult",
        ["share_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_projectvotegroupresult_client_group_id"),
        "projectvotegroupresult",
        ["client_group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("projectvotegroupresult")

    op.create_table(
        "projectvoteobservation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("share_id", sa.Integer(), nullable=True),
        sa.Column("observation_type", sa.String(), nullable=False),
        sa.Column("criterion_id", sa.Integer(), nullable=True),
        sa.Column("item_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response", sa.String(), nullable=False),
        sa.Column("winner_id", sa.Integer(), nullable=True),
        sa.Column("predicted_id", sa.Integer(), nullable=True),
        sa.Column("predicted_probability", sa.Float(), nullable=True),
        sa.Column("prediction_correct", sa.Boolean(), nullable=True),
        sa.Column("client_event_id", sa.String(), nullable=True),
        sa.Column("algorithm_version", sa.String(), nullable=False),
        sa.Column("extra_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("create_date", sa.DateTime(), nullable=True),
        sa.Column("modify_date", sa.DateTime(), nullable=True),
        sa.Column("deleted_date", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("participant_id", "client_event_id", name="uq_vote_obs_client_event"),
    )

    op.add_column(
        "projectvoteparticipant",
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE projectvoteparticipant SET observation_count = COALESCE(comparison_count, 0)"
    )
    op.drop_column("projectvoteparticipant", "comparison_count")
    op.drop_column("projectvoteparticipant", "group_count")
    op.alter_column("projectvoteparticipant", "observation_count", server_default=None)

    op.drop_column("customerproject", "max_recommended_passes")
    op.drop_column("customerproject", "min_expected_passes")
