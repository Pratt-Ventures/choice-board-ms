"""track whether option/factor group sizes were explicitly set

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-08-19 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r9s0t1u2v3w4"
down_revision: Union[str, None] = "q8r9s0t1u2v3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ford_johnson_budget(n: int) -> int:
    import math

    if n <= 1:
        return 0
    total = 0
    for i in range(1, n + 1):
        total += math.ceil(math.log2((3 * i) / 4))
    return int(total)


def _clamp_for_n(value: int, n: int) -> int:
    stored = max(1, min(500, int(value)))
    if n < 2:
        return stored
    fj = _ford_johnson_budget(n)
    pair_cap = n * (n - 1) // 2
    lo = max(1, min(pair_cap, (fj + 1) // 2))
    hi = max(lo, min(pair_cap, fj * 2))
    return max(lo, min(hi, stored))


def _looks_like_default(stored: int, n: int) -> bool:
    if stored == 20:
        return True
    if n < 2:
        return False
    fj = _ford_johnson_budget(n)
    reclamped_legacy = _clamp_for_n(20, n)
    return stored in (fj, reclamped_legacy)


def upgrade() -> None:
    op.add_column(
        "customerproject",
        sa.Column(
            "option_questions_per_group_explicit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "customerproject",
        sa.Column(
            "factor_questions_per_group_explicit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT p.id,
                   p.option_questions_per_group,
                   p.factor_questions_per_group,
                   (
                       SELECT COUNT(*) FROM customerprojectalternatives a
                       WHERE a.project_id = p.id
                         AND a.deleted_date IS NULL
                         AND COALESCE(a.disabled, FALSE) = FALSE
                   ) AS opt_n,
                   (
                       SELECT COUNT(*) FROM customerprojectfactors f
                       WHERE f.project_id = p.id
                         AND f.deleted_date IS NULL
                         AND COALESCE(f.disabled, FALSE) = FALSE
                   ) AS fac_n
            FROM customerproject p
            """
        )
    ).fetchall()
    for row in rows:
        opt_explicit = not _looks_like_default(int(row[1] or 20), int(row[3] or 0))
        fac_explicit = not _looks_like_default(int(row[2] or 20), int(row[4] or 0))
        if not opt_explicit and not fac_explicit:
            continue
        conn.execute(
            sa.text(
                """
                UPDATE customerproject
                SET option_questions_per_group_explicit = :opt_x,
                    factor_questions_per_group_explicit = :fac_x
                WHERE id = :id
                """
            ),
            {"opt_x": opt_explicit, "fac_x": fac_explicit, "id": row[0]},
        )

    op.alter_column("customerproject", "option_questions_per_group_explicit", server_default=None)
    op.alter_column("customerproject", "factor_questions_per_group_explicit", server_default=None)


def downgrade() -> None:
    op.drop_column("customerproject", "factor_questions_per_group_explicit")
    op.drop_column("customerproject", "option_questions_per_group_explicit")
