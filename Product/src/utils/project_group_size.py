"""Persist and retarget option/factor questions-per-group after item changes."""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from .sort_compare import resolve_questions_per_group


def _is_active_row(row: Any) -> bool:
    return not bool(getattr(row, "disabled", False)) and getattr(row, "deleted_date", None) is None


def count_active_options(session: Session, *, project_id: int, customer_id: int) -> int:
    from ..db.models.customer_project_alternatives_criteria import CustomerProjectAlternatives

    rows = session.exec(
        select(CustomerProjectAlternatives).where(
            CustomerProjectAlternatives.project_id == project_id,
            CustomerProjectAlternatives.customer_id == customer_id,
            CustomerProjectAlternatives.deleted_date == None,  # noqa: E711
        )
    ).all()
    return sum(1 for row in rows if _is_active_row(row))


def count_active_factors(session: Session, *, project_id: int, customer_id: int) -> int:
    from ..db.models.customer_project_alternatives_criteria import CustomerProjectFactors

    rows = session.exec(
        select(CustomerProjectFactors).where(
            CustomerProjectFactors.project_id == project_id,
            CustomerProjectFactors.customer_id == customer_id,
            CustomerProjectFactors.deleted_date == None,  # noqa: E711
        )
    ).all()
    return sum(1 for row in rows if _is_active_row(row))


def sync_project_group_sizes(
    session: Session,
    *,
    project_id: int,
    customer_id: int,
    kind: str | None = None,
) -> None:
    from ..db.models.customer_projects import CustomerProject

    project = session.get(CustomerProject, project_id)
    if project is None or project.customer_id != customer_id:
        return
    changed = False
    if kind in (None, "option"):
        n = count_active_options(session, project_id=project_id, customer_id=customer_id)
        nxt = resolve_questions_per_group(
            getattr(project, "option_questions_per_group", None),
            n,
            bool(getattr(project, "option_questions_per_group_explicit", False)),
        )
        if int(project.option_questions_per_group or 0) != nxt:
            project.option_questions_per_group = nxt
            changed = True
    if kind in (None, "factor"):
        n = count_active_factors(session, project_id=project_id, customer_id=customer_id)
        nxt = resolve_questions_per_group(
            getattr(project, "factor_questions_per_group", None),
            n,
            bool(getattr(project, "factor_questions_per_group_explicit", False)),
        )
        if int(project.factor_questions_per_group or 0) != nxt:
            project.factor_questions_per_group = nxt
            changed = True
    if not changed:
        return
    session.add(project)
    previous = session.expire_on_commit
    session.expire_on_commit = False
    try:
        session.commit()
    finally:
        session.expire_on_commit = previous
