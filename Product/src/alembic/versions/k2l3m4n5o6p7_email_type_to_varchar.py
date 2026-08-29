"""store emailactivitylog.email_type as varchar template name

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-08-15 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, None] = "j1k2l3m4n5o6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CURRENT_EMAIL_TYPES = (
    "password_reset",
    "customer_activation_self",
    "customer_activation_admin",
    "customer_activation_admin_activated",
    "new_user_welcome",
    "share_project_vote",
    "share_project_vote_view",
    "share_project_report",
    "magic_access_key",
    "not_set",
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE emailactivitylog ALTER COLUMN email_type TYPE varchar USING email_type::text"
    )
    op.execute("DROP TYPE IF EXISTS outboundemailtype")


def downgrade() -> None:
    known = ", ".join(f"'{name}'" for name in _CURRENT_EMAIL_TYPES)
    op.execute(
        f"UPDATE emailactivitylog SET email_type = 'not_set' "
        f"WHERE email_type NOT IN ({known})"
    )
    outboundemailtype = sa.Enum(*_CURRENT_EMAIL_TYPES, name="outboundemailtype")
    outboundemailtype.create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE emailactivitylog ALTER COLUMN email_type TYPE outboundemailtype "
        "USING email_type::outboundemailtype"
    )
