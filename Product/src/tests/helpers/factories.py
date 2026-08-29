from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field

from sqlmodel import Session

from src.pvf.db.models.api_access_configuration import PvfApiAccessConfiguration
from src.db.models.customer_projects import CustomerProject
from src.db.models.customer_project_alternatives_criteria import (
    CustomerFactorTemplates,
    CustomerProjectAlternatives,
    CustomerProjectFactors,
)
from src.pvf.db.models.customer_user import PvfAccountStatus, PvfCustomer, PvfUser, PvfUserContext
from src.pvf.depends.api_session_dependencies import get_next_session


def uid(prefix: str = "t") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@dataclass
class AccountContext:
    customer: PvfCustomer
    admin: PvfUser
    admin_email: str
    admin_password: str
    member: PvfUser | None = None
    member_email: str | None = None
    member_password: str | None = None
    project: CustomerProject | None = None
    project_tag: str | None = None
    # compatibility aliases used by older tests
    application: CustomerProject | None = None
    application_tag: str | None = None
    api_key_id: str | None = None
    api_rq_key: str | None = None
    api_shared_secret: str | None = None
    tracked_user_ids: list[int] = field(default_factory=list)
    tracked_project_ids: list[int] = field(default_factory=list)
    tracked_app_ids: list[int] = field(default_factory=list)
    tracked_api_key_ids: list[str] = field(default_factory=list)
    tracked_alternative_ids: list[int] = field(default_factory=list)
    tracked_factor_ids: list[int] = field(default_factory=list)
    tracked_template_ids: list[int] = field(default_factory=list)

    def user_context(self, user: PvfUser | None = None) -> PvfUserContext:
        u = user or self.admin
        return PvfUserContext(
            authenticated_session=True,
            sess_user=u,
            sess_customer=self.customer,
        )


def create_account(
    *,
    system_user_mode: int = 0,
    power_user_mode: int = 0,
    with_member: bool = True,
    activated: bool = True,
) -> AccountContext:
    session = get_next_session()
    admin_email = f"{uid('admin')}@example.com"
    admin_password = uid("pw")
    customer = PvfCustomer(
        customer_name=f"Pytest PvfCustomer {uid()}",
        account_status=PvfAccountStatus.active,
        customer_email=admin_email,
        customer_phone="555-0100",
        customer_activated=activated,
    )
    customer = customer.create_customer_system(
        session=session,
        admin_name="Pytest Admin",
        admin_email=admin_email,
        admin_phone="555-0101",
        admin_password=admin_password,
        power_user_mode=power_user_mode,
        system_user_mode=system_user_mode,
        clear_lock=False,
    )
    admin = PvfUser.get_user_by_email_system(session=session, email=admin_email, clear_lock=False)
    ctx = AccountContext(
        customer=customer,
        admin=admin,
        admin_email=admin_email,
        admin_password=admin_password,
        tracked_user_ids=[admin.id],
    )
    session.close()

    if with_member:
        member_email = f"{uid('member')}@example.com"
        member_password = uid("mpw")
        session = get_next_session()
        member_row = PvfUser(
            name="Pytest Member",
            email=member_email,
            phone="555-0102",
            customer_id=customer.id,
            customer_admin=False,
        )
        result = member_row.create_user_system(
            session=session, password=member_password, customer_id=customer.id, clear_lock=False
        )
        member = result.user_info
        ctx.member = member
        ctx.member_email = member_email
        ctx.member_password = member_password
        ctx.tracked_user_ids.append(member.id)
        session.close()

    return ctx


def create_user(
    *,
    session: Session | None = None,
    customer_id: int,
    email: str | None = None,
    password: str | None = None,
    customer_admin: bool = False,
    system_user_mode: int = 0,
    name: str = "Pytest PvfUser",
) -> tuple[PvfUser, str]:
    """Returns (user, password)."""
    close = session is None
    session = session or get_next_session()
    email = email or f"{uid('pvf_user')}@example.com"
    password = password or uid("pw")
    user = PvfUser(
        name=name,
        email=email,
        phone="555-0199",
        customer_id=customer_id,
        customer_admin=customer_admin,
        system_user_mode=system_user_mode,
    )
    result = user.create_user_system(
        session=session, password=password, customer_id=customer_id, clear_lock=False
    )
    if close:
        session.close()
    return result.user_info, password


def create_project(
    ctx: AccountContext, *, tag: str | None = None, title: str | None = None
) -> CustomerProject:
    session = get_next_session()
    tag = tag or uid("proj")
    project = CustomerProject(
        customer_id=ctx.customer.id,
        project_tag=tag,
        project_title=title or "pytest project",
        project_description="pytest project",
        project_created_by=ctx.admin.id,
        disabled=False,
    )
    result = project.create_customer_project(session=session, usr_context=ctx.user_context())
    session.close()
    info = result.customer_project_info
    ctx.project = info
    ctx.project_tag = info.project_tag
    ctx.application = info
    ctx.application_tag = info.project_tag
    ctx.tracked_project_ids.append(info.id)
    ctx.tracked_app_ids.append(info.id)
    return info


def create_application(ctx: AccountContext, *, tag: str | None = None) -> CustomerProject:
    """Compatibility alias for create_project."""
    return create_project(ctx, tag=tag)


def create_alternative(
    ctx: AccountContext,
    *,
    project_id: int | None = None,
    title: str | None = None,
) -> CustomerProjectAlternatives:
    session = get_next_session()
    project_id = project_id or (ctx.project.id if ctx.project else None)
    if project_id is None:
        create_project(ctx)
        project_id = ctx.project.id
    row = CustomerProjectAlternatives(
        customer_id=ctx.customer.id,
        project_id=project_id,
        alternative_title=title or f"Alt {uid()}",
        alternative_description="pytest alternative",
    )
    result = row.create_alternative(session=session, usr_context=ctx.user_context())
    session.close()
    info = result.alternative_info
    ctx.tracked_alternative_ids.append(info.id)
    return info


def create_factor(
    ctx: AccountContext,
    *,
    project_id: int | None = None,
    title: str | None = None,
) -> CustomerProjectFactors:
    session = get_next_session()
    project_id = project_id or (ctx.project.id if ctx.project else None)
    if project_id is None:
        create_project(ctx)
        project_id = ctx.project.id
    row = CustomerProjectFactors(
        customer_id=ctx.customer.id,
        project_id=project_id,
        factor_title=title or f"Factor {uid()}",
        factor_description="pytest factor",
        factor_polarity_positive=True,
    )
    result = row.create_factor(session=session, usr_context=ctx.user_context())
    session.close()
    info = result.factor_info
    ctx.tracked_factor_ids.append(info.id)
    return info


def create_factor_template(
    ctx: AccountContext,
    *,
    title: str | None = None,
    enable_global_share: bool = False,
    use_with_projects: bool = False,
    use_with_options: bool = False,
    use_with_factors: bool = True,
) -> CustomerFactorTemplates:
    session = get_next_session()
    row = CustomerFactorTemplates(
        customer_id=ctx.customer.id,
        factor_template_title=title or f"Template {uid()}",
        factor_template_description="pytest template",
        factor_template_entries=[{"factor_title": "Cost", "factor_polarity_positive": False}],
        enable_global_share=enable_global_share,
        use_with_projects=use_with_projects,
        use_with_options=use_with_options,
        use_with_factors=use_with_factors,
    )
    result = row.create_factor_template(session=session, usr_context=ctx.user_context())
    session.close()
    info = result.factor_template_info
    ctx.tracked_template_ids.append(info.id)
    return info


def create_api_key(
    ctx: AccountContext,
    *,
    application_tag: str | None = None,
    active_status: bool = True,
) -> tuple[str, str, str]:
    """Returns (authentication_key_id, rq_key, shared_secret)."""
    session = get_next_session()
    application_tag = application_tag or ctx.project_tag or ctx.application_tag or uid("app")
    shared_secret = f"ss-{secrets.token_urlsafe(32)}"
    config = PvfApiAccessConfiguration(
        description="pytest key",
        active_status=active_status,
        customer_id=ctx.customer.id,
        application_tag=application_tag,
        user_id=ctx.admin.id,
        shared_secret=shared_secret,
        webhook_endpoint="",
    )
    result = config.create_api_configuration_entry(session=session, usr_context=ctx.user_context())
    session.close()
    key_id = result.api_configuration_info.authentication_key_id
    rq_key = result.api_configuration_request_authentication
    secret = result.api_configuration_info.shared_secret
    ctx.api_key_id = key_id
    ctx.api_rq_key = rq_key
    ctx.api_shared_secret = secret
    ctx.tracked_api_key_ids.append(key_id)
    return key_id, rq_key, secret
