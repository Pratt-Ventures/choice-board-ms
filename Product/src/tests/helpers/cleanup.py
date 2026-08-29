from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from src.pvf.db.models.api_access_configuration import PvfApiAccessConfiguration
from src.db.models.customer_projects import CustomerProject
from src.db.models.customer_project_alternatives_criteria import (
    CustomerFactorTemplates,
    CustomerProjectAlternatives,
    CustomerProjectFactors,
)
from src.pvf.db.models.user_communication import PvfBugReport, PvfSuggestion
from src.pvf.db.models.customer_user import PvfAccountStatus, PvfCustomer, PvfUser
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.factories import AccountContext


def cleanup_account(ctx: AccountContext) -> None:
    """Best-effort cascade: keys, project content, projects, users, then deactivate customer."""
    session = get_next_session()
    try:
        for key_id in list(ctx.tracked_api_key_ids):
            row = session.exec(
                select(PvfApiAccessConfiguration).where(PvfApiAccessConfiguration.authentication_key_id == key_id)
            ).one_or_none()
            if row is not None:
                session.delete(row)

        for alt_id in list(getattr(ctx, "tracked_alternative_ids", [])):
            row = session.exec(select(CustomerProjectAlternatives).where(CustomerProjectAlternatives.id == alt_id)).one_or_none()
            if row is not None and row.deleted_date is None:
                row.deleted_date = datetime.now()
                session.add(row)

        for factor_id in list(getattr(ctx, "tracked_factor_ids", [])):
            row = session.exec(select(CustomerProjectFactors).where(CustomerProjectFactors.id == factor_id)).one_or_none()
            if row is not None and row.deleted_date is None:
                row.deleted_date = datetime.now()
                session.add(row)

        for template_id in list(getattr(ctx, "tracked_template_ids", [])):
            row = session.exec(select(CustomerFactorTemplates).where(CustomerFactorTemplates.id == template_id)).one_or_none()
            if row is not None and row.deleted_date is None:
                row.deleted_date = datetime.now()
                session.add(row)

        project_ids = list(getattr(ctx, "tracked_project_ids", []) or getattr(ctx, "tracked_app_ids", []))
        for project_id in project_ids:
            row = session.exec(select(CustomerProject).where(CustomerProject.id == project_id)).one_or_none()
            if row is not None and row.deleted_date is None:
                row.deleted_date = datetime.now()
                session.add(row)

        for user_id in list(ctx.tracked_user_ids):
            row = session.exec(select(PvfUser).where(PvfUser.id == user_id)).one_or_none()
            if row is not None and row.deleted_date is None:
                row.deleted_date = datetime.now()
                row.access_disabled = 1
                session.add(row)

        if ctx.customer is not None and ctx.customer.id is not None:
            for model in (PvfBugReport, PvfSuggestion):
                for row in session.exec(select(model).where(model.customer_id == ctx.customer.id)).all():
                    if row.deleted_date is None:
                        row.deleted_date = datetime.now()
                        session.add(row)
            cust = session.exec(select(PvfCustomer).where(PvfCustomer.id == ctx.customer.id)).one_or_none()
            if cust is not None:
                cust.account_status = PvfAccountStatus.inactive
                cust.customer_activated = False
                cust.customer_email = f"deleted-{cust.id}-{cust.customer_email}"
                session.add(cust)

        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
