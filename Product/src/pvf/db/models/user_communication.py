from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import Column, Index, LargeBinary, func
from sqlalchemy.orm import defer
from sqlmodel import Field, Session, SQLModel, select

from ...bindings.pvf_invocation import runtime_settings
from .customer_user import PvfCustomer, PvfUser, PvfUserContext
from ...utils.log_event import log_event
from ...utils.pvf_base_internal_resources import PvfWsResultPackage

KIND_BUG_REPORT = "bug_report"
KIND_SUGGESTION = "suggestion"

IMPACT_VALUES = ("minor", "moderate", "blocking")
IMPORTANCE_VALUES = ("nice_to_have", "important", "very_important")
PRODUCT_AREA_VALUES = (
    "projects",
    "sharing",
    "compare",
    "results",
    "templates",
    "team",
    "account",
    "other",
)

MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
ALLOWED_ATTACHMENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "application/pdf",
}

_WINDOW = timedelta(hours=24)


class PvfUserCommunicationLifecycle(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True)
    user_id: int = Field(index=True)
    acknowledge_date: datetime | None = Field(default=None)
    acknowledge_user_id: int | None = Field(default=None)
    acknowledge_note: str | None = Field(default=None)
    response_date: datetime | None = Field(default=None)
    response_user_id: int | None = Field(default=None)
    response_note: str | None = Field(default=None)
    resolution_date: datetime | None = Field(default=None)
    resolution_user_id: int | None = Field(default=None)
    resolution_note: str | None = Field(default=None)
    attachment_filename: str | None = Field(default=None)
    attachment_content_type: str | None = Field(default=None)
    create_date: datetime = Field(default_factory=datetime.now)
    modify_date: datetime = Field(default_factory=datetime.now)
    deleted_date: datetime | None = Field(default=None)


class PvfBugReport(PvfUserCommunicationLifecycle, table=True):
    __tablename__ = "pvf_bugreport"
    summary: str
    what_happened: str
    expected_happened: str | None = Field(default=None)
    steps_to_reproduce: str | None = Field(default=None)
    impact: str | None = Field(default=None)
    attachment_bytes: bytes | None = Field(default=None, sa_column=Column(LargeBinary, nullable=True))

    __table_args__ = (
        Index("ix_pvf_bugreport_user_create", "user_id", "create_date"),
        Index("ix_pvf_bugreport_customer_create", "customer_id", "create_date"),
        Index("ix_pvf_bugreport_deleted_create", "deleted_date", "create_date"),
    )


class PvfSuggestion(PvfUserCommunicationLifecycle, table=True):
    __tablename__ = "pvf_suggestion"
    suggestion: str
    accomplish_goal: str | None = Field(default=None)
    product_area: str | None = Field(default=None)
    importance: str | None = Field(default=None)
    attachment_bytes: bytes | None = Field(default=None, sa_column=Column(LargeBinary, nullable=True))

    __table_args__ = (
        Index("ix_pvf_suggestion_user_create", "user_id", "create_date"),
        Index("ix_pvf_suggestion_customer_create", "customer_id", "create_date"),
        Index("ix_pvf_suggestion_deleted_create", "deleted_date", "create_date"),
    )


class PvfUserCommunicationRow(BaseModel):
    id: int
    kind: str
    customer_id: int
    user_id: int
    customer_name: str | None = None
    user_name: str | None = None
    has_attachment: bool = False
    attachment_filename: str | None = None
    attachment_content_type: str | None = None
    summary: str | None = None
    what_happened: str | None = None
    expected_happened: str | None = None
    steps_to_reproduce: str | None = None
    impact: str | None = None
    suggestion: str | None = None
    accomplish_goal: str | None = None
    product_area: str | None = None
    importance: str | None = None
    acknowledge_date: datetime | None = None
    acknowledge_user_id: int | None = None
    acknowledge_note: str | None = None
    response_date: datetime | None = None
    response_user_id: int | None = None
    response_note: str | None = None
    resolution_date: datetime | None = None
    resolution_user_id: int | None = None
    resolution_note: str | None = None
    create_date: datetime | None = None
    modify_date: datetime | None = None


class PvfUserCommunicationSubmitResult(PvfWsResultPackage):
    stored: bool = False
    limit_warning: bool = False
    submitted_in_window: int = 0
    max_per_day: int = 10
    submission_id: int | None = None


class PvfUserCommunicationResult_One(PvfWsResultPackage):
    item: PvfUserCommunicationRow | None = None


class PvfUserCommunicationResult_Many(PvfWsResultPackage):
    items: list[PvfUserCommunicationRow] | None = None
    total_count: int = 0


class PvfUserCommunicationDeleteResult(PvfWsResultPackage):
    success: bool = False
    submission_id: int | None = None


class AdminRetrieveForm(BaseModel):
    offset: int = PydanticField(default=0, ge=0)
    limit: int = PydanticField(default=25, ge=1, le=100)


class AdminModifyForm(BaseModel):
    id: int
    acknowledge_date_action: Literal["set", "clear"] | None = None
    response_date_action: Literal["set", "clear"] | None = None
    resolution_date_action: Literal["set", "clear"] | None = None
    acknowledge_note: str | None = None
    response_note: str | None = None
    resolution_note: str | None = None


class SubmissionIdForm(BaseModel):
    id: int


def _label_for_kind(kind: str) -> str:
    return "bug reports" if kind == KIND_BUG_REPORT else "suggestions"


def _title_of(row: Any, kind: str) -> str:
    if kind == KIND_BUG_REPORT:
        return (getattr(row, "summary", None) or "")[:200]
    return (getattr(row, "suggestion", None) or "")[:200]


def row_from_model(row: Any, kind: str, *, customer_name: str | None = None, user_name: str | None = None) -> PvfUserCommunicationRow:
    data = row.model_dump(exclude={"attachment_bytes"})
    data["kind"] = kind
    data["customer_name"] = customer_name
    data["user_name"] = user_name
    data["has_attachment"] = bool(row.attachment_filename)
    return PvfUserCommunicationRow.model_validate(data)


def enrich_rows(session: Session, rows: list[Any], kind: str) -> list[PvfUserCommunicationRow]:
    if not rows:
        return []
    user_ids = {int(r.user_id) for r in rows if r.user_id is not None}
    customer_ids = {int(r.customer_id) for r in rows if r.customer_id is not None}
    users: dict[int, str] = {}
    customers: dict[int, str] = {}
    if user_ids:
        for user in session.exec(select(PvfUser).where(PvfUser.id.in_(user_ids))).all():
            users[int(user.id)] = user.name
    if customer_ids:
        for customer in session.exec(select(PvfCustomer).where(PvfCustomer.id.in_(customer_ids))).all():
            customers[int(customer.id)] = customer.customer_name
    return [
        row_from_model(
            row,
            kind,
            customer_name=customers.get(int(row.customer_id)),
            user_name=users.get(int(row.user_id)),
        )
        for row in rows
    ]


def count_in_window(session: Session, model: type[SQLModel], user_id: int) -> int:
    cutoff = datetime.now() - _WINDOW
    return int(
        session.exec(
            select(func.count())
            .select_from(model)
            .where(model.user_id == user_id, model.create_date >= cutoff)
        ).one()
        or 0
    )


def validate_attachment(filename: str | None, content_type: str | None, data: bytes | None) -> str:
    if data is None:
        return ""
    if len(data) > MAX_ATTACHMENT_BYTES:
        return "Attachment must be 8 MB or smaller"
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in ALLOWED_ATTACHMENT_TYPES:
        return "Attachment must be an image (PNG, JPEG, WebP, GIF) or a PDF"
    if not (filename or "").strip():
        return "Attachment filename is required"
    return ""


def submit_row(
    session: Session,
    *,
    model: type[SQLModel],
    kind: str,
    usr_context: PvfUserContext,
    fields: dict[str, Any],
    attachment_filename: str | None = None,
    attachment_content_type: str | None = None,
    attachment_bytes: bytes | None = None,
) -> PvfUserCommunicationSubmitResult:
    max_per_day = int(runtime_settings().MAX_REPORTS_PER_DAY)
    n_before = count_in_window(session, model, usr_context.sess_user.id)
    type_label = _label_for_kind(kind)
    if n_before >= max_per_day + 1:
        title = fields.get("summary") or fields.get("suggestion") or ""
        log_id = log_event(
            f"PvfUser communication {kind} discarded due to daily submission limits",
            usr_context=usr_context,
            severity=2,
            details_json={
                "type": kind,
                "title": str(title)[:200],
                "fields": {k: v for k, v in fields.items() if v not in (None, "")},
                "filename": attachment_filename,
            },
        )
        return PvfUserCommunicationSubmitResult(
            stored=False,
            limit_warning=False,
            submitted_in_window=n_before,
            max_per_day=max_per_day,
            failure_reason="The request was discarded due to daily submission limits.",
            log_id=log_id,
        )

    now = datetime.now()
    row = model(
        customer_id=usr_context.sess_user.customer_id,
        user_id=usr_context.sess_user.id,
        attachment_filename=attachment_filename,
        attachment_content_type=attachment_content_type,
        attachment_bytes=attachment_bytes,
        create_date=now,
        modify_date=now,
        **fields,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    n_after = n_before + 1
    warning = n_after > max_per_day
    return PvfUserCommunicationSubmitResult(
        stored=True,
        limit_warning=warning,
        submitted_in_window=n_after,
        max_per_day=max_per_day,
        submission_id=row.id,
        failure_reason=f"You've reached the daily submission limit for {type_label}." if warning else "",
    )


def list_scoped(
    session: Session,
    *,
    model: type[SQLModel],
    kind: str,
    usr_context: PvfUserContext,
) -> PvfUserCommunicationResult_Many:
    query = select(model).options(defer(model.attachment_bytes)).where(model.deleted_date == None)  # noqa: E711
    if usr_context.sess_user.customer_admin:
        query = query.where(model.customer_id == usr_context.sess_user.customer_id)
    else:
        query = query.where(model.user_id == usr_context.sess_user.id)
    query = query.order_by(model.create_date.desc())
    rows = list(session.exec(query).all())
    items = enrich_rows(session, rows, kind)
    return PvfUserCommunicationResult_Many(items=items, total_count=len(items))


def admin_list(
    session: Session,
    *,
    model: type[SQLModel],
    kind: str,
    offset: int,
    limit: int,
) -> PvfUserCommunicationResult_Many:
    filters = model.deleted_date == None  # noqa: E711
    total = int(session.exec(select(func.count()).select_from(model).where(filters)).one() or 0)
    rows = list(
        session.exec(
            select(model)
            .options(defer(model.attachment_bytes))
            .where(filters)
            .order_by(model.create_date.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return PvfUserCommunicationResult_Many(items=enrich_rows(session, rows, kind), total_count=total)


def get_by_id(session: Session, *, model: type[SQLModel], submission_id: int, load_bytes: bool = False) -> Any | None:
    query = select(model).where(model.id == submission_id)
    if not load_bytes:
        query = query.options(defer(model.attachment_bytes))
    return session.exec(query.limit(1)).one_or_none()


def can_view_row(row: Any, usr_context: PvfUserContext) -> bool:
    user = usr_context.sess_user
    if user.system_user_mode >= 2:
        return True
    if user.customer_admin and row.customer_id == user.customer_id:
        return True
    return row.user_id == user.id


def has_admin_stamp(row: Any) -> bool:
    return any((row.acknowledge_date, row.response_date, row.resolution_date))


def can_owner_delete(row: Any, usr_context: PvfUserContext) -> bool:
    if usr_context.sess_user.system_user_mode >= 2:
        return True
    if row.user_id != usr_context.sess_user.id:
        return False
    return not has_admin_stamp(row)


def apply_admin_modify(
    session: Session,
    *,
    model: type[SQLModel],
    kind: str,
    usr_context: PvfUserContext,
    form: AdminModifyForm,
) -> PvfUserCommunicationResult_One:
    row = get_by_id(session, model=model, submission_id=form.id)
    if row is None or row.deleted_date is not None:
        log_id = log_event(
            f"admin modify {kind} id={form.id} not found",
            usr_context=usr_context,
            severity=2,
        )
        return PvfUserCommunicationResult_One(failure_reason="Submission not found", log_id=log_id)
    now = datetime.now()
    actor_id = usr_context.sess_user.id
    for action_name, date_attr, user_attr in (
        ("acknowledge_date_action", "acknowledge_date", "acknowledge_user_id"),
        ("response_date_action", "response_date", "response_user_id"),
        ("resolution_date_action", "resolution_date", "resolution_user_id"),
    ):
        action = getattr(form, action_name)
        if action == "set":
            setattr(row, date_attr, now)
            setattr(row, user_attr, actor_id)
        elif action == "clear":
            setattr(row, date_attr, None)
            setattr(row, user_attr, None)
    if "acknowledge_note" in form.model_fields_set:
        row.acknowledge_note = form.acknowledge_note
    if "response_note" in form.model_fields_set:
        row.response_note = form.response_note
    if "resolution_note" in form.model_fields_set:
        row.resolution_note = form.resolution_note
    row.modify_date = now
    session.add(row)
    session.commit()
    session.refresh(row)
    items = enrich_rows(session, [row], kind)
    return PvfUserCommunicationResult_One(item=items[0] if items else None)


def soft_delete(
    session: Session,
    *,
    model: type[SQLModel],
    kind: str,
    usr_context: PvfUserContext,
    submission_id: int,
) -> PvfUserCommunicationDeleteResult:
    row = get_by_id(session, model=model, submission_id=submission_id)
    if row is None or row.deleted_date is not None:
        log_id = log_event(
            f"delete {kind} id={submission_id} not found",
            usr_context=usr_context,
            severity=2,
        )
        return PvfUserCommunicationDeleteResult(
            success=False,
            submission_id=submission_id,
            failure_reason="Submission not found",
            log_id=log_id,
        )
    if not can_owner_delete(row, usr_context):
        log_id = log_event(
            f"delete {kind} id={submission_id} denied",
            usr_context=usr_context,
            severity=3,
        )
        return PvfUserCommunicationDeleteResult(
            success=False,
            submission_id=submission_id,
            failure_reason="Not allowed to delete this submission",
            log_id=log_id,
        )
    row.deleted_date = datetime.now()
    row.modify_date = datetime.now()
    session.add(row)
    session.commit()
    return PvfUserCommunicationDeleteResult(success=True, submission_id=row.id)
