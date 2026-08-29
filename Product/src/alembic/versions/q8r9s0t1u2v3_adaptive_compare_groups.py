"""ranking mode + in-progress adaptive compare groups

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-08-19 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q8r9s0t1u2v3"
down_revision: Union[str, None] = "p7q8r9s0t1u2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customerproject",
        sa.Column("ranking_mode", sa.String(), nullable=False, server_default="rank_all"),
    )
    op.execute(
        "UPDATE customerproject SET ranking_mode = 'find_best' WHERE project_exclusive_mode IS TRUE"
    )
    op.alter_column("customerproject", "ranking_mode", server_default=None)

    op.add_column("projectvotegroupresult", sa.Column("group_token", sa.String(), nullable=True))
    op.add_column(
        "projectvotegroupresult",
        sa.Column("status", sa.String(), nullable=False, server_default="complete"),
    )
    op.add_column(
        "projectvotegroupresult",
        sa.Column("requested_pairing_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "projectvotegroupresult",
        sa.Column("received_pairing_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "projectvotegroupresult",
        sa.Column("historical_pairing_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "projectvotegroupresult",
        sa.Column("ranking_target", sa.String(), nullable=False, server_default="full"),
    )
    op.add_column("projectvotegroupresult", sa.Column("top_n", sa.Integer(), nullable=True))
    op.add_column(
        "projectvotegroupresult",
        sa.Column("batch_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE projectvotegroupresult SET received_pairing_count = comparison_count "
        "WHERE comparison_count IS NOT NULL"
    )
    op.execute(
        "UPDATE projectvotegroupresult SET requested_pairing_count = comparison_count "
        "WHERE comparison_count IS NOT NULL"
    )
    op.execute(
        "UPDATE projectvotegroupresult SET group_token = client_group_id "
        "WHERE group_token IS NULL AND client_group_id IS NOT NULL"
    )
    op.create_index(
        "ix_projectvotegroupresult_group_token",
        "projectvotegroupresult",
        ["group_token"],
        unique=True,
    )
    op.alter_column("projectvotegroupresult", "status", server_default=None)
    op.alter_column("projectvotegroupresult", "requested_pairing_count", server_default=None)
    op.alter_column("projectvotegroupresult", "received_pairing_count", server_default=None)
    op.alter_column("projectvotegroupresult", "historical_pairing_count", server_default=None)
    op.alter_column("projectvotegroupresult", "ranking_target", server_default=None)
    op.alter_column("projectvotegroupresult", "batch_index", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_projectvotegroupresult_group_token", table_name="projectvotegroupresult")
    op.drop_column("projectvotegroupresult", "batch_index")
    op.drop_column("projectvotegroupresult", "top_n")
    op.drop_column("projectvotegroupresult", "ranking_target")
    op.drop_column("projectvotegroupresult", "historical_pairing_count")
    op.drop_column("projectvotegroupresult", "received_pairing_count")
    op.drop_column("projectvotegroupresult", "requested_pairing_count")
    op.drop_column("projectvotegroupresult", "status")
    op.drop_column("projectvotegroupresult", "group_token")
    op.drop_column("customerproject", "ranking_mode")
