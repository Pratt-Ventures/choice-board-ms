from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from ..bindings.pvf_invocation import runtime_settings
from ..db.models.user_communication import (
    IMPACT_VALUES,
    IMPORTANCE_VALUES,
    KIND_BUG_REPORT,
    KIND_SUGGESTION,
    PRODUCT_AREA_VALUES,
    AdminModifyForm,
    AdminRetrieveForm,
    PvfBugReport,
    SubmissionIdForm,
    PvfSuggestion,
    PvfUserCommunicationDeleteResult,
    PvfUserCommunicationResult_Many,
    PvfUserCommunicationResult_One,
    PvfUserCommunicationSubmitResult,
    admin_list,
    apply_admin_modify,
    can_view_row,
    get_by_id,
    list_scoped,
    soft_delete,
    submit_row,
    validate_attachment,
)
from ..depends.api_session_dependencies import SessionDep
from ..depends.check_user_session_jwt_dependencies import UserAccessDep
from ..utils.log_event import log_event

router = APIRouter()

_TAG = "user-communication"


def _require_feature(usr_context) -> None:
    if getattr(runtime_settings(), "ACTIVATE_CUSTOMER_COMMUNICATION", False):
        return
    log_event(
        "PvfUser communication is not enabled",
        usr_context=usr_context,
        severity=2,
        raise_exception=HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PvfUser communication is not enabled",
        ),
    )


def _require_sysadmin(usr_context) -> None:
    if usr_context.sess_user.system_user_mode >= 2:
        return
    log_event(
        "Unauthorized user communication admin attempt",
        usr_context=usr_context,
        severity=3,
        raise_exception=HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized",
        ),
    )


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _norm_choice(value: str | None, allowed: tuple[str, ...], label: str) -> tuple[str | None, str]:
    text = _norm(value)
    if text is None:
        return None, ""
    lowered = text.lower()
    if lowered not in allowed:
        return None, f"Invalid {label}"
    return lowered, ""


def _read_attachment(file: UploadFile | None) -> tuple[str | None, str | None, bytes | None, str]:
    if file is None or not file.filename:
        return None, None, None, ""
    data = file.file.read()
    if not data:
        return None, None, None, ""
    filename = file.filename
    content_type = file.content_type
    err = validate_attachment(filename, content_type, data)
    if err:
        return None, None, None, err
    return filename, content_type, data, ""


@router.post(
    "/user-comm/bug-report-submit",
    summary="Submit a bug report",
    description="Any logged-in user. Optional screenshot or file. Rate-limited per day.",
    tags=[_TAG],
)
def bug_report_submit(
    session: SessionDep,
    usr_context: UserAccessDep,
    summary: str = Form(..., description="Short summary of the bug"),
    what_happened: str = Form(..., description="What happened"),
    expected_happened: str | None = Form(None, description="What did you expect to happen"),
    steps_to_reproduce: str | None = Form(None, description="Steps to reproduce"),
    impact: str | None = Form(None, description="Impact: minor, moderate, or blocking"),
    file: UploadFile | None = File(None),
) -> PvfUserCommunicationSubmitResult:
    _require_feature(usr_context)
    summary_n = _norm(summary)
    happened_n = _norm(what_happened)
    if not summary_n or not happened_n:
        return PvfUserCommunicationSubmitResult(failure_reason="Summary and what happened are required")
    impact_n, impact_err = _norm_choice(impact, IMPACT_VALUES, "impact")
    if impact_err:
        return PvfUserCommunicationSubmitResult(failure_reason=impact_err)
    filename, content_type, data, attach_err = _read_attachment(file)
    if attach_err:
        return PvfUserCommunicationSubmitResult(failure_reason=attach_err)
    return submit_row(
        session,
        model=PvfBugReport,
        kind=KIND_BUG_REPORT,
        usr_context=usr_context,
        fields={
            "summary": summary_n,
            "what_happened": happened_n,
            "expected_happened": _norm(expected_happened),
            "steps_to_reproduce": _norm(steps_to_reproduce),
            "impact": impact_n,
        },
        attachment_filename=filename,
        attachment_content_type=content_type,
        attachment_bytes=data,
    )


@router.post(
    "/user-comm/suggestion-submit",
    summary="Submit a suggestion",
    description="Any logged-in user. Optional attachment. Rate-limited per day.",
    tags=[_TAG],
)
def suggestion_submit(
    session: SessionDep,
    usr_context: UserAccessDep,
    suggestion: str = Form(..., description="The suggestion"),
    accomplish_goal: str | None = Form(None, description="What would this help you accomplish"),
    product_area: str | None = Form(None, description="Area of the product"),
    importance: str | None = Form(None, description="Importance: nice_to_have, important, or very_important"),
    file: UploadFile | None = File(None),
) -> PvfUserCommunicationSubmitResult:
    _require_feature(usr_context)
    suggestion_n = _norm(suggestion)
    if not suggestion_n:
        return PvfUserCommunicationSubmitResult(failure_reason="PvfSuggestion is required")
    area_n, area_err = _norm_choice(product_area, PRODUCT_AREA_VALUES, "area of the product")
    if area_err:
        return PvfUserCommunicationSubmitResult(failure_reason=area_err)
    importance_n, importance_err = _norm_choice(importance, IMPORTANCE_VALUES, "importance")
    if importance_err:
        return PvfUserCommunicationSubmitResult(failure_reason=importance_err)
    filename, content_type, data, attach_err = _read_attachment(file)
    if attach_err:
        return PvfUserCommunicationSubmitResult(failure_reason=attach_err)
    return submit_row(
        session,
        model=PvfSuggestion,
        kind=KIND_SUGGESTION,
        usr_context=usr_context,
        fields={
            "suggestion": suggestion_n,
            "accomplish_goal": _norm(accomplish_goal),
            "product_area": area_n,
            "importance": importance_n,
        },
        attachment_filename=filename,
        attachment_content_type=content_type,
        attachment_bytes=data,
    )


@router.post(
    "/user-comm/bug-report-retrieve",
    summary="Retrieve bug reports",
    description="Members see their own. Workspace admins see all active reports for the workspace.",
    tags=[_TAG],
)
def bug_report_retrieve(
    session: SessionDep,
    usr_context: UserAccessDep,
) -> PvfUserCommunicationResult_Many:
    _require_feature(usr_context)
    return list_scoped(session, model=PvfBugReport, kind=KIND_BUG_REPORT, usr_context=usr_context)


@router.post(
    "/user-comm/suggestion-retrieve",
    summary="Retrieve suggestions",
    description="Members see their own. Workspace admins see all active suggestions for the workspace.",
    tags=[_TAG],
)
def suggestion_retrieve(
    session: SessionDep,
    usr_context: UserAccessDep,
) -> PvfUserCommunicationResult_Many:
    _require_feature(usr_context)
    return list_scoped(session, model=PvfSuggestion, kind=KIND_SUGGESTION, usr_context=usr_context)


@router.post(
    "/user-comm/bug-report-admin-retrieve",
    summary="System admin: paginated bug reports",
    description="System admins only. Most recent first.",
    tags=[_TAG],
)
def bug_report_admin_retrieve(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: AdminRetrieveForm,
) -> PvfUserCommunicationResult_Many:
    _require_feature(usr_context)
    _require_sysadmin(usr_context)
    return admin_list(session, model=PvfBugReport, kind=KIND_BUG_REPORT, offset=form.offset, limit=form.limit)


@router.post(
    "/user-comm/suggestion-admin-retrieve",
    summary="System admin: paginated suggestions",
    description="System admins only. Most recent first.",
    tags=[_TAG],
)
def suggestion_admin_retrieve(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: AdminRetrieveForm,
) -> PvfUserCommunicationResult_Many:
    _require_feature(usr_context)
    _require_sysadmin(usr_context)
    return admin_list(session, model=PvfSuggestion, kind=KIND_SUGGESTION, offset=form.offset, limit=form.limit)


@router.post(
    "/user-comm/bug-report-admin-modify",
    summary="System admin: update bug report lifecycle",
    description="Set or clear acknowledge, response, and resolution dates. Notes can be edited independently.",
    tags=[_TAG],
)
def bug_report_admin_modify(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: AdminModifyForm,
) -> PvfUserCommunicationResult_One:
    _require_feature(usr_context)
    _require_sysadmin(usr_context)
    return apply_admin_modify(session, model=PvfBugReport, kind=KIND_BUG_REPORT, usr_context=usr_context, form=form)


@router.post(
    "/user-comm/suggestion-admin-modify",
    summary="System admin: update suggestion lifecycle",
    description="Set or clear acknowledge, response, and resolution dates. Notes can be edited independently.",
    tags=[_TAG],
)
def suggestion_admin_modify(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: AdminModifyForm,
) -> PvfUserCommunicationResult_One:
    _require_feature(usr_context)
    _require_sysadmin(usr_context)
    return apply_admin_modify(session, model=PvfSuggestion, kind=KIND_SUGGESTION, usr_context=usr_context, form=form)


@router.post(
    "/user-comm/bug-report-delete",
    summary="Soft-delete a bug report",
    description="Owners may delete their own report before any admin action. System admins may delete any report.",
    tags=[_TAG],
)
def bug_report_delete(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: SubmissionIdForm,
) -> PvfUserCommunicationDeleteResult:
    _require_feature(usr_context)
    return soft_delete(session, model=PvfBugReport, kind=KIND_BUG_REPORT, usr_context=usr_context, submission_id=form.id)


@router.post(
    "/user-comm/suggestion-delete",
    summary="Soft-delete a suggestion",
    description="Owners may delete their own suggestion before any admin action. System admins may delete any suggestion.",
    tags=[_TAG],
)
def suggestion_delete(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: SubmissionIdForm,
) -> PvfUserCommunicationDeleteResult:
    _require_feature(usr_context)
    return soft_delete(session, model=PvfSuggestion, kind=KIND_SUGGESTION, usr_context=usr_context, submission_id=form.id)


def _attachment_response(session, usr_context, model, kind: str, submission_id: int):
    row = get_by_id(session, model=model, submission_id=submission_id, load_bytes=True)
    if row is None or row.deleted_date is not None or not can_view_row(row, usr_context):
        log_event(
            f"{kind} attachment id={submission_id} not visible",
            usr_context=usr_context,
            severity=2,
            raise_exception=HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"),
        )
    if not row.attachment_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No attachment")
    filename = row.attachment_filename or "attachment"
    return Response(
        content=bytes(row.attachment_bytes),
        media_type=row.attachment_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=300",
        },
    )


@router.get(
    "/user-comm/bug-report-attachment/{submission_id}",
    summary="Download a bug report attachment",
    tags=[_TAG],
)
def bug_report_attachment(
    session: SessionDep,
    usr_context: UserAccessDep,
    submission_id: int,
):
    _require_feature(usr_context)
    return _attachment_response(session, usr_context, PvfBugReport, KIND_BUG_REPORT, submission_id)


@router.get(
    "/user-comm/suggestion-attachment/{submission_id}",
    summary="Download a suggestion attachment",
    tags=[_TAG],
)
def suggestion_attachment(
    session: SessionDep,
    usr_context: UserAccessDep,
    submission_id: int,
):
    _require_feature(usr_context)
    return _attachment_response(session, usr_context, PvfSuggestion, KIND_SUGGESTION, submission_id)
