from __future__ import annotations

from datetime import datetime, timezone
import time

from pydantic import BaseModel, Field
from sqlmodel import Session, select, desc, func
from sqlalchemy import case

from fastapi import APIRouter

from ..pvf.bindings.pvf_services import PvfWsResultPackage, PvfCustomer, PvfUser, SessionDep, UserAccessDep, PvfApiAccessConfiguration

from ..db.models.customer_projects import CustomerProject


router = APIRouter()


class RequestDashboardEntries(BaseModel):
    recent_limit: int = Field(default=10, ge=1, le=50, description="Max items for recent lists")
    project_tag: str | None = Field(default=None, description="Optional filter limiting scoped sections to one project tag")
    application_tag: str | None = Field(default=None, description="Deprecated alias for project_tag")


class ApiKeyCountByTag(BaseModel):
    application_tag: str
    total: int = 0
    active: int = 0


class DashboardSummary(BaseModel):
    project_count: int = 0
    project_active_count: int = 0
    application_count: int = 0
    application_active_count: int = 0
    api_key_count: int = 0
    api_key_active_count: int = 0
    team_user_count: int = 0
    api_key_count_by_tag: list[ApiKeyCountByTag] = Field(default_factory=list)


class ProjectDashboardRow(BaseModel):
    id: int
    project_tag: str
    project_title: str | None = None
    project_description: str | None = None
    disabled: bool = False
    create_date: datetime | None = None
    modify_date: datetime | None = None


class ApplicationDashboardRow(BaseModel):
    """Compatibility alias shape for older clients."""
    id: int
    application_tag: str
    application_description: str | None = None
    disabled: bool = False
    create_date: datetime | None = None
    modify_date: datetime | None = None


class ApiKeyDashboardRow(BaseModel):
    id: int
    description: str | None = None
    application_tag: str
    active_status: bool = True
    has_webhook: bool = False
    create_date: datetime | None = None


class PrimaryAccountStatus(BaseModel):
    customer_id: int
    customer_name: str | None = None
    customer_email: str | None = None
    account_status: str | None = None
    customer_activated: bool = False
    stripe_customer_id: str | None = None
    trial_expiration_date: datetime | None = None
    service_expiration_date: datetime | None = None
    trial_expiration_days: int | None = None
    sandbox_count: int | None = 0


class DashboardEntriesView(PvfWsResultPackage):
    process_time: float = Field(default=0.0, description="The time taken to process the request in seconds")
    generated_at: datetime | None = Field(default=None, description="UTC timestamp when the snapshot was assembled")
    summary: DashboardSummary = Field(default_factory=DashboardSummary)
    projects_summary: list[ProjectDashboardRow] = Field(default_factory=list)
    applications_summary: list[ApplicationDashboardRow] = Field(default_factory=list)
    api_keys_summary: list[ApiKeyDashboardRow] = Field(default_factory=list)
    account_status: PrimaryAccountStatus | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _enum_value(value) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


@router.post(
    "/core/get-dashboard-information",
    summary="Return package of entries for quick dashboard views",
    description=(
        "Returns a dashboard snapshot: project and API key counts, "
        "project/API key summaries, and primary account status."
    ),
    tags=["dashboard"],
)
def get_dashboard_info(
    session: SessionDep,
    usr_context: UserAccessDep,
    dashboard_request: RequestDashboardEntries,
) -> DashboardEntriesView:
    return get_dashboard_info_sync(
        session=session,
        usr_context=usr_context,
        dashboard_request=dashboard_request,
    )


def get_dashboard_info_sync(
    session: Session,
    usr_context: UserAccessDep,
    dashboard_request: RequestDashboardEntries,
) -> DashboardEntriesView:
    start_request_time = time.time()
    now = _utcnow()
    customer_id = usr_context.sess_user.customer_id
    limit = dashboard_request.recent_limit
    project_tag = dashboard_request.project_tag or dashboard_request.application_tag
    project_tag = project_tag if project_tag not in (None, "", "string") else None

    result = DashboardEntriesView(generated_at=datetime.now(timezone.utc))

    customer = usr_context.sess_customer
    if customer is None:
        customer = session.exec(select(PvfCustomer).where(PvfCustomer.id == customer_id).limit(1)).one_or_none()
        usr_context.sess_customer = customer

    if customer is not None:
        trial_expiration_days = None
        if customer.customer_account in (None, "") and customer.trial_expiration_date is not None:
            trial_exp = _as_naive(customer.trial_expiration_date)
            if trial_exp is not None:
                days_left = (trial_exp - now).days
                if days_left >= 0:
                    trial_expiration_days = days_left
        result.account_status = PrimaryAccountStatus(
            customer_id=customer.id,
            customer_name=customer.customer_name,
            customer_email=customer.customer_email,
            account_status=_enum_value(customer.account_status),
            customer_activated=bool(customer.customer_activated),
            stripe_customer_id=customer.customer_account,
            trial_expiration_date=customer.trial_expiration_date,
            service_expiration_date=customer.service_expiration_date,
            trial_expiration_days=trial_expiration_days,
            sandbox_count=customer.sandbox_count or 0,
        )

    project_query = select(CustomerProject).where(
        CustomerProject.customer_id == customer_id,
        CustomerProject.deleted_date == None,  # noqa: E711
    )
    if project_tag is not None:
        project_query = project_query.where(CustomerProject.project_tag == project_tag)
    projects = list(session.exec(project_query.order_by(CustomerProject.project_tag)).all())

    key_base = [PvfApiAccessConfiguration.customer_id == customer_id]
    if project_tag is not None:
        key_base.append(PvfApiAccessConfiguration.application_tag == project_tag)

    api_keys = list(
        session.exec(
            select(PvfApiAccessConfiguration)
            .where(*key_base)
            .order_by(desc(PvfApiAccessConfiguration.create_date))
            .limit(limit)
        ).all()
    )
    result.api_keys_summary = [
        ApiKeyDashboardRow(
            id=k.id,
            description=k.description,
            application_tag=k.application_tag,
            active_status=bool(k.active_status),
            has_webhook=bool(k.webhook_endpoint),
            create_date=k.create_date,
        )
        for k in api_keys
    ]

    key_count_total = session.exec(
        select(func.count()).select_from(PvfApiAccessConfiguration).where(*key_base)
    ).one()
    key_count_active = session.exec(
        select(func.count()).select_from(PvfApiAccessConfiguration).where(
            *key_base, PvfApiAccessConfiguration.active_status == True  # noqa: E712
        )
    ).one()
    key_tag_rows = session.exec(
        select(
            PvfApiAccessConfiguration.application_tag,
            func.count().label("total"),
            func.sum(case((PvfApiAccessConfiguration.active_status == True, 1), else_=0)).label("active"),  # noqa: E712
        )
        .where(*key_base)
        .group_by(PvfApiAccessConfiguration.application_tag)
    ).all()
    api_key_count_by_tag = [
        ApiKeyCountByTag(application_tag=tag or "", total=int(total or 0), active=int(active or 0))
        for tag, total, active in key_tag_rows
    ]

    team_user_count = session.exec(
        select(func.count()).select_from(PvfUser).where(
            PvfUser.customer_id == customer_id,
            PvfUser.deleted_date == None,  # noqa: E711
        )
    ).one()

    project_active_count = sum(1 for p in projects if not p.disabled)

    project_rows: list[ProjectDashboardRow] = []
    app_compat_rows: list[ApplicationDashboardRow] = []
    for project in projects:
        project_rows.append(
            ProjectDashboardRow(
                id=project.id,
                project_tag=project.project_tag,
                project_title=project.project_title,
                project_description=project.project_description,
                disabled=bool(project.disabled),
                create_date=project.create_date,
                modify_date=project.modify_date,
            )
        )
        app_compat_rows.append(
            ApplicationDashboardRow(
                id=project.id,
                application_tag=project.project_tag,
                application_description=project.project_description,
                disabled=bool(project.disabled),
                create_date=project.create_date,
                modify_date=project.modify_date,
            )
        )
    project_rows.sort(key=lambda r: r.project_tag or "")
    app_compat_rows.sort(key=lambda r: r.application_tag or "")
    result.projects_summary = project_rows[: max(limit, 5)]
    result.applications_summary = app_compat_rows[: max(limit, 5)]

    count = len(projects)
    result.summary = DashboardSummary(
        project_count=count,
        project_active_count=project_active_count,
        application_count=count,
        application_active_count=project_active_count,
        api_key_count=int(key_count_total or 0),
        api_key_active_count=int(key_count_active or 0),
        team_user_count=int(team_user_count or 0),
        api_key_count_by_tag=api_key_count_by_tag,
    )

    result.process_time = time.time() - start_request_time
    return result
