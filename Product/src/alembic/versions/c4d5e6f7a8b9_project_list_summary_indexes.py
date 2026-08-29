"""project_list_summary_indexes

Composite indexes for lean project list/summary queries.

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-08-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_customerproject_customer_deleted",
        "customerproject",
        ["customer_id", "deleted_date"],
        unique=False,
    )
    op.create_index(
        "ix_projectvoteobservation_customer_project_deleted",
        "projectvoteobservation",
        ["customer_id", "project_id", "deleted_date"],
        unique=False,
    )
    op.create_index(
        "ix_projectvoteparticipant_customer_project_deleted",
        "projectvoteparticipant",
        ["customer_id", "project_id", "deleted_date"],
        unique=False,
    )
    op.create_index(
        "ix_customerprojectalternatives_customer_project_deleted",
        "customerprojectalternatives",
        ["customer_id", "project_id", "deleted_date"],
        unique=False,
    )
    op.create_index(
        "ix_customerprojectfactors_customer_project_deleted",
        "customerprojectfactors",
        ["customer_id", "project_id", "deleted_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_customerprojectfactors_customer_project_deleted", table_name="customerprojectfactors")
    op.drop_index("ix_customerprojectalternatives_customer_project_deleted", table_name="customerprojectalternatives")
    op.drop_index("ix_projectvoteparticipant_customer_project_deleted", table_name="projectvoteparticipant")
    op.drop_index("ix_projectvoteobservation_customer_project_deleted", table_name="projectvoteobservation")
    op.drop_index("ix_customerproject_customer_deleted", table_name="customerproject")
