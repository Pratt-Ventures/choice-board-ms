"""Share link management and the share access gate (framework-generic).

Authenticated share CRUD plus the cookie/magic-key gate engine used by share-link
access endpoints. Application-specific behavior is bound through hooks registered on
the PvfInvocation (see pvf.pvf_invocation.PvfHookRegistry):

  - entity_resolver: validate/name the shared entity
  - share_type_email_dispatcher: invitation email type per share type
  - share_resend_email_dispatcher: administrator resend email type per share type
  - share_action_matrix: valid access operations per share type
  - share_mutating_operations: operations requiring an established cookie
  - share_activity_enricher: application stats on activity rows
  - share_email_params_enricher: application template params on share emails
"""
from __future__ import annotations
from typing import Union
from datetime import datetime, timedelta
from urllib.parse import quote
from pydantic import BaseModel, ConfigDict, Field
import re
import base64
import numpy as np

from sqlmodel import Session, select

from fastapi import APIRouter, status, HTTPException, Request, Response

from ..depends.api_session_dependencies import SessionDep
from ..depends.check_user_session_jwt_dependencies import UserAccessDep
from ..db.models.customer_user import PvfUser, PvfUserContext
from ..config.pvf_config_settings import pvf_settings as settings
from ..bindings.pvf_invocation import get_hooks
from ..utils.log_event import log_event
from ..utils.pvf_base_internal_resources import PvfWsResultPackage
from ..utils.utils_show import show_vars_semi
from ..utils.outbound_mail_queue import send_outbound_mail
from ..utils.utils_general import get_hex_hash_from_args
from ..utils.pvf_base_internal_resources import PvfAuthRelatedOutboundEmailType
from ..utils.share_gate_throttle import (
    credential_failure_exceeded,
    record_credential_failure,
    record_unauth_hit,
    unauth_volume_exceeded,
)

from ..db.models.share_link_tracking import (
    PvfShareLinkBase, PvfShareLink, PvfShareLinkAccessed, PvfShareLinkMagicKey,
    PvfShareAccessCheckMode, PvfShareLinkResult_One_Id,
    PvfShareLinkResult_One,
    get_share_access_operations, get_share_object_actions,
)
from ..db.models.email_activity_log import PvfEmailActivityLog


class PvfShareAccessRequest_Base(BaseModel):
    display_name: str | None = Field(default=None, description="supplies a user name/display name for verification, which is not checked, but captured")
    verification_email: str | None = Field(default=None, description="supplies email expected for verification")
    verification_password: str | None = Field(default=None, description="supplies password expected for verification")
    verification_magic_email_key: str | None = Field(default=None, description="A magic key that authenticates to a provided email")
    authorize_verification_email: bool = Field(default=False, description="If True, and not authorized, an email with a magic access link is sent")

class PvfShareAccessRequest(PvfShareAccessRequest_Base):
    requested_target_token: str | None = Field(default=None, description="Magic token for the share link being accessed")
    requested_target_share_type: str | None = Field(default="not_set", description="Share type of the target (one of the application's share object actions)")
    requested_target_share_operation: str | None = Field(default="not_set", description="Sub-operation being performed (one of the application's share access operations)")
    request_logout: bool = Field(default=False, description="If True, clear the share cookie only")
    verify_link_id: int | None = Field(default=None, description="If set, the resolved share link id must match")

class PvfShareAccessDenied_Base(PvfWsResultPackage):
    access_mode: PvfShareAccessCheckMode = Field(default=PvfShareAccessCheckMode.not_specified, description="Indicates the access mode for this link")
    verification_password_needed: bool = Field(default=False)
    verification_email_needed: bool = Field(default=False)
    verification_original_email_needed: bool = Field(default=False)
    verification_email_send_link_mode: bool = Field(default=False)
    verification_email_magic_link_needed: bool = Field(default=False)
    verification_acknowledge_agreement_needed: bool = Field(default=False)
    verification_password_not_supplied: bool = Field(default=False)
    verification_password_incorrect: bool = Field(default=False)
    verification_email_not_supplied: bool = Field(default=False)
    verification_magic_link_incorrect: bool = Field(default=False)
    verification_magic_link_expired: bool = Field(default=False)
    verification_magic_link_used: bool = Field(default=False)
    sent_magic_access_message: bool = Field(default=False)

class PvfShareAccessConfirmed_Base(PvfWsResultPackage):
    access_mode: PvfShareAccessCheckMode
    access_type: str = Field(default="not_set")
    access_operation: str = Field(default="not_set")
    viewer_organization_name: str | None = Field(default=None)
    viewer_personal_name: str | None = Field(default=None)
    viewer_captured_email: str | None = Field(default=None)
    is_email_verified: bool = Field(default=False)
    link_access_id: int = Field(default=-1)
    link_access_count: int = Field(default=-1)
    link_magic_key_id: int = Field(default=-1)
    shared_entity_db_id: int = Field(default=-1)
    shared_entity_magic_token: str = Field(default="")
    share_id: int = Field(default=-1)

class ExtendOrDisableShareLink(BaseModel):
    share_id: Union[int, None] = Field(default=None, description='Specifies id value for share link to be disabled')
    magic_token: Union[str, None] = Field(default=None, description='Specifies magic token value for share link to be disabled')
    share_link_enabled: bool | None = Field(default=None, description="False to disable, True to enable; changed if specified")
    share_link_expiration: int | None = Field(default=None, description="Days the link should be active from creation; changed if specified")

class CreateShareLinkResponse(PvfShareLinkResult_One):
    link_url: str | None = Field(default=None, description="The full URL to access the shared link, if available")
    link_email_sent: bool | None = Field(default=None, description="True when link_auto_send was requested and the invitation email was delivered successfully")

class SendShareInvitationRequest(BaseModel):
    share_id: int | None = Field(default=None, description="Share id to send or resend the invitation for")
    magic_token: str | None = Field(default=None, description="Share magic token when share id is not provided")

class SendShareInvitationResponse(PvfWsResultPackage):
    link_email_sent: bool | None = Field(default=None, description="True when the invitation email was delivered")
    was_resend: bool = Field(default=False, description="True when a prior invitation had already been delivered for this share")
    email_type: str | None = Field(default=None, description="Outbound message type used for this delivery")

class ShareLink_Auths_Accesses(BaseModel):
    # extra="allow" so the application's share_activity_enricher hook can attach
    # application-specific stats (e.g. participant/observation counts) to each entry
    model_config = ConfigDict(extra="allow")

    project_id: int = Field(default=-1, description="The primary id of the shared entity")
    share_id: int = Field(default=-1, description="The primary id of the share link")
    share_link: PvfShareLink | None = Field(default=None)
    share_link_magic_keys: list[PvfShareLinkMagicKey] = Field(default_factory=list)
    share_link_accesses: list[PvfShareLinkAccessed] = Field(default_factory=list)
    share_link_url: str | None = Field(default="")
    password_set: bool = Field(default=False, description="True when a share password was configured (plaintext never returned)")
    session_count: int = Field(default=0, description="Unique access sessions (cookie rows)")
    total_hits: int = Field(default=0, description="Sum of access_count across sessions")
    magic_keys_issued: int = Field(default=0)
    magic_keys_used: int = Field(default=0)
    history_open: bool = Field(default=False, description="Client UI convenience; unused server-side")
    invite_email_sent: bool = Field(default=False, description="True when an invitation or resend email was previously delivered for this share")
    invite_email_last_sent: datetime | None = Field(default=None, description="Most recent invitation or resend delivery time, if any")
    share_link_expired: bool = Field(default=False, description="True when the share has passed its expiration window")

class ShareActivityResultsSingle(PvfWsResultPackage):
    share_info_list: list[ShareLink_Auths_Accesses] = Field(default_factory=list)
    unknown_keys: list[PvfShareLinkMagicKey] = Field(default_factory=list)
    unknown_accesses: list[PvfShareLinkAccessed] = Field(default_factory=list)

class ShareActivityResultsMulti(PvfWsResultPackage):
    share_info_list_per_project_id: dict[int, list[ShareLink_Auths_Accesses]] = Field(default_factory=dict)
    unknown_keys: list[PvfShareLinkMagicKey] = Field(default_factory=list)
    unknown_accesses: list[PvfShareLinkAccessed] = Field(default_factory=list)


def _valid_share_types() -> list[str]:
    return [action for action in get_share_object_actions() if action != "not_set"]


def _valid_operations() -> list[str]:
    return [operation for operation in get_share_access_operations() if operation != "not_set"]


def _normalize_cookie_field(value) -> str:
    if value is None:
        return ""
    return str(value)

def get_token_cookie(request: Request):
    view_token = view_cookie_display_name = view_cookie_email = make_cookies_better = None
    try:
        view_cookie_package_encoded = request.cookies.get(settings.ACCESS_VIEW_COOKIE)
        if view_cookie_package_encoded not in ("", None):
            view_cookie_package_clear = base64.b64decode(view_cookie_package_encoded.encode('ascii')).decode('ascii')
            view_cookie_parts = view_cookie_package_clear.split('|')
        else:
            view_cookie_parts = []
        if len(view_cookie_parts) == 4:
            view_token = view_cookie_parts[0]
            view_cookie_display_name = _normalize_cookie_field(view_cookie_parts[1])
            view_cookie_email = _normalize_cookie_field(view_cookie_parts[2])
            make_cookies_better = view_cookie_parts[3]
    except Exception:
        pass
    return view_token, view_cookie_display_name, view_cookie_email, make_cookies_better

def make_token_cookie(*, shared_magic_token, display_name, email, make_cookies_better: int=None) -> tuple[str, str]:
    display_name = _normalize_cookie_field(display_name)
    email = _normalize_cookie_field(email)
    if make_cookies_better is None:
        make_cookies_better = np.random.randint(10000, 99999)
    expected_cookie_token = get_hex_hash_from_args(settings.VIEW_TOKEN_KEY, settings.ACCESS_VIEW_COOKIE, shared_magic_token, display_name, email, str(make_cookies_better), settings.VIEW_TOKEN_KEY)
    cookie_clear_payload = f"{expected_cookie_token}|{display_name}|{email}|{make_cookies_better}"
    cookie_encoded_payload = base64.b64encode(cookie_clear_payload.encode("ascii")).decode('ascii')
    return expected_cookie_token, cookie_encoded_payload

def _share_cookie_secure() -> bool:
    return bool(settings.is_prod())

_COOKIE_UNLIMITED_SECONDS = 10 * 365 * 24 * 3600
_SHARE_GATE_THROTTLE_DETAIL = "Too many access attempts. Please try again later."


def build_share_landing_url(*, share_type: str, magic_token: str, access_magic_key: str | None = None) -> str:
    base = (
        f"{settings.APPLICATION_BASE_URL}"
        f"{settings.SHARE_PROJECT_APP_VIEW_BASE_URL}{share_type}/"
        f"{magic_token}{settings.SHARE_PROJECT_APP_VIEW_SUFFIX_URL}"
    )
    if access_magic_key:
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}key={quote(str(access_magic_key), safe='')}"
    return base


def share_cookie_max_age_seconds(cookie_duration: int | None) -> int:
    """Honor per-link cookie_duration (days). <0 is long-lived; 0/None uses the server default."""
    days = cookie_duration
    if days is None:
        days = settings.SHARE_LINK_COOKIE_EXPIRATION_DAYS
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = settings.SHARE_LINK_COOKIE_EXPIRATION_DAYS
    if days < 0:
        return _COOKIE_UNLIMITED_SECONDS
    if days == 0:
        days = settings.SHARE_LINK_COOKIE_EXPIRATION_DAYS
    return max(1, days) * 3600 * 24


def _request_remote_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _raise_share_gate_throttled():
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=_SHARE_GATE_THROTTLE_DETAIL,
        headers={"Retry-After": "60"},
    )


def _enforce_unauth_volume(request: Request):
    ip = _request_remote_ip(request)
    if unauth_volume_exceeded(ip):
        _raise_share_gate_throttled()
    record_unauth_hit(ip)


def _note_credential_failure(request: Request, magic_token: str | None):
    ip = _request_remote_ip(request)
    if credential_failure_exceeded(ip, magic_token):
        _raise_share_gate_throttled()
    record_credential_failure(ip, magic_token)


def _clear_share_cookie(response: Response, shared_magic_token: str):
    response.set_cookie(settings.ACCESS_VIEW_COOKIE, "", httponly=True,
                        max_age=0,
                        path=f"{settings.SHARE_WS_BASE_URL}{shared_magic_token}/", samesite="strict", secure=_share_cookie_secure())

def _security_note_for_mode(access_mode: PvfShareAccessCheckMode) -> str | None:
    mapping = {
        PvfShareAccessCheckMode.open_access: settings.SHARE_SECURITY_NOTE_OPEN_ACCESS,
        PvfShareAccessCheckMode.email_any_unverified: settings.SHARE_SECURITY_NOTE_EMAIL_ANY_UNVERIFIED,
        PvfShareAccessCheckMode.email_any_verified: settings.SHARE_SECURITY_NOTE_EMAIL_ANY_VERIFIED,
        PvfShareAccessCheckMode.email_matching: settings.SHARE_SECURITY_NOTE_EMAIL_MATCHING,
        PvfShareAccessCheckMode.email_matching_verified: settings.SHARE_SECURITY_NOTE_EMAIL_MATCHING_VERIFIED,
        PvfShareAccessCheckMode.recipient_email_verified: settings.SHARE_SECURITY_NOTE_RECIPIENT_EMAIL_VERIFIED,
        PvfShareAccessCheckMode.password_only: settings.SHARE_SECURITY_NOTE_PASSWORD_ONLY,
        PvfShareAccessCheckMode.password_with_email_any_unverified: settings.SHARE_SECURITY_NOTE_PASSWORD_WITH_EMAIL_ANY_UNVERIFIED,
        PvfShareAccessCheckMode.password_with_email_any_verified: settings.SHARE_SECURITY_NOTE_PASSWORD_WITH_EMAIL_ANY_VERIFIED,
        PvfShareAccessCheckMode.password_with_email_matching: settings.SHARE_SECURITY_NOTE_PASSWORD_WITH_EMAIL_MATCHING,
        PvfShareAccessCheckMode.password_with_email_matching_verified: settings.SHARE_SECURITY_NOTE_PASSWORD_WITH_EMAIL_MATCHING_VERIFIED,
        PvfShareAccessCheckMode.password_with_recipient_email_verified: settings.SHARE_SECURITY_NOTE_PASSWORD_WITH_RECIPIENT_EMAIL_VERIFIED,
    }
    return mapping.get(access_mode)

_PASSWORD_ACCESS_MODES = (
    PvfShareAccessCheckMode.password_only,
    PvfShareAccessCheckMode.password_with_email_any_unverified,
    PvfShareAccessCheckMode.password_with_email_any_verified,
    PvfShareAccessCheckMode.password_with_email_matching,
    PvfShareAccessCheckMode.password_with_email_matching_verified,
    PvfShareAccessCheckMode.password_with_recipient_email_verified,
)

_SHARE_INVITE_EMAIL_TYPES = (
    "share_project_vote",
    "share_project_vote_view",
    "share_project_report",
    "resending_invitation",
)


def _share_link_is_expired(link: PvfShareLink) -> bool:
    if link.share_link_expiration is None or link.share_link_expiration < 0:
        return False
    if link.create_date is None:
        return False
    created = link.create_date
    if getattr(created, "tzinfo", None) is not None:
        created = created.replace(tzinfo=None)
    return created + timedelta(days=int(link.share_link_expiration)) < datetime.now()


def _valid_duration_message(exp_days: int | None) -> str:
    if exp_days is None:
        return settings.SHARE_LINK_EXPIRATION_MESSAGE
    if exp_days < 0:
        return "no time limit"
    return f"{exp_days} day" + ("" if exp_days == 1 else "s")


def _share_invitation_email_params(*, link: PvfShareLink, link_url: str, share_password_note: str) -> dict:
    return dict(
        shared_with_company=link.shared_with_company_name,
        shared_with_name=link.shared_with_person_name,
        valid_duration=_valid_duration_message(link.share_link_expiration),
        project_id=link.shared_entity_db_id,
        project_name=link.share_link_name,
        security_note=_security_note_for_mode(link.access_mode),
        share_password_note=share_password_note,
        magic_token=link.magic_token,
        url_prefix=f"{settings.SHARE_PROJECT_APP_VIEW_BASE_URL}{link.shared_type}/",
        url_suffix=settings.SHARE_PROJECT_APP_VIEW_SUFFIX_URL,
        url=link_url,
        share_id=link.id,
        shared_type=str(link.shared_type),
    )


def _can_manage_share_invitation(usr_context: PvfUserContext, link: PvfShareLink) -> bool:
    user = usr_context.sess_user
    if user is None or link.customer_id != user.customer_id:
        return False
    if user.customer_admin or (getattr(user, "system_user_mode", 0) or 0) >= 2:
        return True
    return user.id == link.user_id


def _latest_invite_send_by_token(session: Session, customer_id: int, shares: list[PvfShareLink]) -> dict[str, datetime]:
    emails = {
        (share.shared_with_email or "").strip().lower()
        for share in shares
        if (share.shared_with_email or "").strip()
    }
    tokens = {share.magic_token for share in shares if share.magic_token}
    if not emails or not tokens:
        return {}
    rows = session.exec(
        select(PvfEmailActivityLog)
        .where(
            PvfEmailActivityLog.customer_id == customer_id,
            PvfEmailActivityLog.email_address.in_(list(emails)),
            PvfEmailActivityLog.email_type.in_(_SHARE_INVITE_EMAIL_TYPES),
        )
        .order_by(PvfEmailActivityLog.id.desc())
    ).all()
    latest: dict[str, datetime] = {}
    for row in rows:
        token = (row.email_params_json or {}).get("magic_token")
        if token in tokens and token not in latest:
            latest[str(token)] = row.create_date
    return latest


def _normalize_email_type_name(email_type) -> str | None:
    if email_type is None:
        return None
    return str(getattr(email_type, "value", email_type))

router = APIRouter()

@router.post('/create-share-link',
             summary="Create a share link for external access to a shared entity",
             tags=['share'])
def create_new_shared_link_wrapper(session: SessionDep, usr_context: UserAccessDep, share_link_request: PvfShareLinkBase) -> CreateShareLinkResponse:
    return create_new_shared_link(session=session, usr_context=usr_context, share_link_request=share_link_request)


def create_new_shared_link(session: SessionDep, usr_context: UserAccessDep, share_link_request: PvfShareLinkBase) -> CreateShareLinkResponse:
    hooks = get_hooks()
    share_link = PvfShareLink(**share_link_request.model_dump())
    share_link.user_id = usr_context.sess_user.id
    share_link.customer_id = usr_context.sess_user.customer_id

    if share_link_request.share_link_name is not None:
        share_link.share_link_name = share_link_request.share_link_name

    if share_link.shared_type not in _valid_share_types():
        log_id = log_event(f"Invalid type of share requested {share_link.shared_type}", usr_context=usr_context, severity=3)
        return CreateShareLinkResponse(failure_reason=f"Invalid type of share requested {share_link.shared_type}", log_id=log_id)

    email_type = None
    if hooks.share_type_email_dispatcher is not None:
        email_type = hooks.share_type_email_dispatcher(share_link.shared_type)
    if share_link.link_auto_send and email_type is None:
        log_id = log_event(f"No invitation email type registered for share type {share_link.shared_type}", usr_context=usr_context, severity=3)
        return CreateShareLinkResponse(failure_reason=f"Share type {share_link.shared_type} does not support invitation emails", log_id=log_id)

    share_password_note = ""
    if share_link.access_mode in _PASSWORD_ACCESS_MODES:
        if share_link.share_password_in_email:
            share_password_note = settings.SHARE_SECURITY_PASSWORD_INCLUDED_NOTE.format(share_password=share_link.share_password)
        else:
            share_password_note = settings.SHARE_SECURITY_PASSWORD_SEPARATE_NOTE

    if _security_note_for_mode(share_link.access_mode) is None:
        log_id = log_event(f"Unrecognized share access_mode {share_link.access_mode} in share request {share_link.shared_type}", usr_context=usr_context, severity=3)
        return CreateShareLinkResponse(failure_reason=f"Unrecognized share access_mode {share_link.access_mode} in share request {share_link.shared_type} ({log_id})")

    create_result = share_link.create_shared_link_record(session=session, usr_context=usr_context)
    return_share_link_data = CreateShareLinkResponse(
        failure_reason=create_result.failure_reason,
        log_id=create_result.log_id,
        link_info=create_result.link_info,
    )
    if return_share_link_data.link_info is None or return_share_link_data.failure_reason not in (None, ""):
        return return_share_link_data

    return_share_link_data.link_url = build_share_landing_url(
        share_type=str(return_share_link_data.link_info.shared_type),
        magic_token=return_share_link_data.link_info.magic_token or "",
    )

    if return_share_link_data.link_info.link_auto_send:
        email_params = _share_invitation_email_params(
            link=return_share_link_data.link_info,
            link_url=return_share_link_data.link_url or "",
            share_password_note=share_password_note,
        )
        if hooks.share_email_params_enricher is not None:
            email_params = hooks.share_email_params_enricher(return_share_link_data.link_info, email_params)
        result = send_outbound_mail(session=session,
                                    usr_context=usr_context,
                                    email_type=email_type,
                                    destination_email=return_share_link_data.link_info.shared_with_email,
                                    email_params=email_params,
                                    )
        # send_outbound_mail now returns "" (sent), "queued:<id>" (queued), or error string (failed)
        if result == "" or (isinstance(result, str) and result.startswith("queued:")):
            # queued is not failure; only mark sent when confirmed
            if result == "":
                return_share_link_data.link_email_sent = True
            else:
                # queued -> not yet confirmed, leave link_email_sent False/None but not failure
                return_share_link_data.link_email_sent = False
                # Optionally surface queued id in log
                show_vars_semi(f'share create email queued {result} for {return_share_link_data.link_info.shared_with_email}')
        elif result not in ("", None):
            return_share_link_data.failure_reason = 'Link request succeeded, but we could not send an email notification - please try again.'
    elif not settings.is_prod():
        show_vars_semi(f'ISSUED share link token {return_share_link_data.link_url} for entity {return_share_link_data.link_info.share_link_name}/{return_share_link_data.link_info.shared_entity_db_id}')
    return return_share_link_data

@router.post('/extend-or-disable-share-link',
             summary="Extend, Disable, or Reenable a previously issued shared link by id or magic_token",
             tags=['share'])
def extend_or_disable_shared_link(session: SessionDep, usr_context: UserAccessDep, share_link_update: ExtendOrDisableShareLink) -> PvfShareLinkResult_One_Id:
    share_link_info = PvfShareLink.get_shared_link_by_id_or_magic_token_system(session=session, usr_context=usr_context, shared_link_id=share_link_update.share_id, shared_magic_token=share_link_update.magic_token, clear_lock=False, allow_disabled_link_retrieval=True)
    if share_link_info.failure_reason not in ("", None):
        return PvfShareLinkResult_One_Id(failure_reason=share_link_info.failure_reason, log_id=share_link_info.log_id)
    if share_link_update.share_link_enabled is not None:
        share_link_info.link_info.share_link_enabled = share_link_update.share_link_enabled
    if share_link_update.share_link_expiration is not None:
        share_link_info.link_info.share_link_expiration = share_link_update.share_link_expiration
    update_result = share_link_info.link_info.update_shared_link_record(session=session, usr_context=usr_context)
    if update_result.failure_reason not in ("", None):
        return PvfShareLinkResult_One_Id(failure_reason=update_result.failure_reason, log_id=update_result.log_id)
    return PvfShareLinkResult_One_Id(link_id=update_result.link_info.id if update_result.link_info else None)


@router.post('/send-share-invitation',
             summary="Send or resend the invitation email for an existing share link",
             tags=['share'])
def send_share_invitation(
    session: SessionDep,
    usr_context: UserAccessDep,
    share_invite_request: SendShareInvitationRequest,
) -> SendShareInvitationResponse:
    if share_invite_request.share_id is None and share_invite_request.magic_token in (None, ""):
        log_id = log_event("Send share invitation requested without share id or magic token", usr_context=usr_context, severity=3)
        return SendShareInvitationResponse(failure_reason="Share id or magic token is required", log_id=log_id)

    share_link_info = PvfShareLink.get_shared_link_by_id_or_magic_token_system(
        session=session,
        usr_context=usr_context,
        shared_link_id=share_invite_request.share_id,
        shared_magic_token=share_invite_request.magic_token,
        clear_lock=False,
        allow_disabled_link_retrieval=True,
    )
    if share_link_info.failure_reason not in ("", None) or share_link_info.link_info is None:
        return SendShareInvitationResponse(failure_reason=share_link_info.failure_reason or "Share link was not found", log_id=share_link_info.log_id)

    link_info = share_link_info.link_info
    if not _can_manage_share_invitation(usr_context, link_info):
        log_event(
            f"Unauthorized attempt to send invitation for share {link_info.id}",
            usr_context=usr_context,
            severity=3,
            raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized attempt to send a share invitation"),
        )

    if not link_info.share_link_enabled:
        log_id = log_event(f"Invitation send refused for disabled share {link_info.id}", usr_context=usr_context, severity=2)
        return SendShareInvitationResponse(failure_reason="This share link is disabled and cannot be sent", log_id=log_id)

    if _share_link_is_expired(link_info):
        log_id = log_event(f"Invitation send refused for expired share {link_info.id}", usr_context=usr_context, severity=2)
        return SendShareInvitationResponse(failure_reason="This share link has expired and cannot be sent", log_id=log_id)

    destination_email = (link_info.shared_with_email or "").strip()
    if not destination_email:
        log_id = log_event(f"Invitation send refused for share {link_info.id} with no recipient email", usr_context=usr_context, severity=2)
        return SendShareInvitationResponse(failure_reason="This share has no recipient email", log_id=log_id)

    hooks = get_hooks()
    first_send_type = None
    if hooks.share_type_email_dispatcher is not None:
        first_send_type = hooks.share_type_email_dispatcher(link_info.shared_type)
    if first_send_type is None:
        log_id = log_event(f"No invitation email type registered for share type {link_info.shared_type}", usr_context=usr_context, severity=3)
        return SendShareInvitationResponse(failure_reason=f"Share type {link_info.shared_type} does not support invitation emails", log_id=log_id)

    prior_sends = _latest_invite_send_by_token(session, usr_context.sess_user.customer_id, [link_info])
    was_resend = bool(link_info.magic_token and link_info.magic_token in prior_sends)
    email_type = first_send_type
    if was_resend and hooks.share_resend_email_dispatcher is not None:
        resend_type = hooks.share_resend_email_dispatcher(link_info.shared_type)
        if resend_type is not None:
            email_type = resend_type

    share_password_note = ""
    if link_info.access_mode in _PASSWORD_ACCESS_MODES:
        share_password_note = settings.SHARE_SECURITY_PASSWORD_SEPARATE_NOTE

    if _security_note_for_mode(link_info.access_mode) is None:
        log_id = log_event(f"Unrecognized share access_mode {link_info.access_mode} for share {link_info.id}", usr_context=usr_context, severity=3)
        return SendShareInvitationResponse(failure_reason=f"Unrecognized share access_mode {link_info.access_mode}", log_id=log_id)

    link_url = build_share_landing_url(
        share_type=str(link_info.shared_type),
        magic_token=link_info.magic_token or "",
    )
    email_params = _share_invitation_email_params(
        link=link_info,
        link_url=link_url,
        share_password_note=share_password_note,
    )
    if hooks.share_email_params_enricher is not None:
        email_params = hooks.share_email_params_enricher(link_info, email_params)

    result = send_outbound_mail(
        session=session,
        usr_context=usr_context,
        email_type=email_type,
        destination_email=destination_email,
        email_params=email_params,
    )
    if result == "":
        return SendShareInvitationResponse(
            link_email_sent=True,
            was_resend=was_resend,
            email_type=_normalize_email_type_name(email_type),
        )
    if isinstance(result, str) and result.startswith("queued:"):
        # queued -> not failed, but not yet confirmed
        return SendShareInvitationResponse(
            link_email_sent=False,
            was_resend=was_resend,
            email_type=_normalize_email_type_name(email_type),
        )
    return SendShareInvitationResponse(
        failure_reason="We could not send an email notification - please try again.",
        was_resend=was_resend,
        email_type=_normalize_email_type_name(email_type),
    )


def share_link_validate_and_log(*, session: Session,
                                    share_usr_context: PvfUserContext,
                                    request: Request,
                                    response: Response,
                                    share_request: PvfShareAccessRequest,
                                    ) -> tuple[PvfShareAccessConfirmed_Base | PvfShareAccessDenied_Base, PvfShareLink | None, PvfShareLinkAccessed | None]:
    hooks = get_hooks()
    action_matrix = hooks.share_action_matrix or {}
    if share_request.requested_target_share_type in _valid_share_types():
        valid_operations = action_matrix.get(share_request.requested_target_share_type) or _valid_operations()
        if share_request.requested_target_share_operation not in valid_operations:
            log_event(f"Unrecognized internal share request access mode {share_request.requested_target_share_type} access {share_request.requested_target_share_operation}",
                               usr_context=share_usr_context, severity=3, raise_exception=True)
        external_base_url = f'{settings.SHARE_PROJECT_APP_VIEW_BASE_URL}{share_request.requested_target_share_type}/'
        external_suffix_url = settings.SHARE_PROJECT_APP_VIEW_SUFFIX_URL
    else:
        log_event(f"Unrecognized internal share request type {share_request.requested_target_share_type} access {share_request.requested_target_share_operation}",
                    usr_context=share_usr_context, severity=3, raise_exception=True)

    # Follow-up operations that mutate state require an existing cookie
    follow_up_use_existing_cookie_only = share_request.requested_target_share_operation in (hooks.share_mutating_operations or [])

    view_token, view_cookie_display_name, view_cookie_email, make_cookies_better = get_token_cookie(request)
    expected_cookie_token, _ = make_token_cookie(shared_magic_token=share_request.requested_target_token,
                                                 display_name=view_cookie_display_name,
                                                 email=view_cookie_email,
                                                 make_cookies_better=make_cookies_better)
    if view_token is not None and expected_cookie_token != view_token:
        log_id = log_event(f"Invalid header token received {view_token} vs expected {expected_cookie_token}", severity=4, usr_context=share_usr_context)
        _clear_share_cookie(response, share_request.requested_target_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access view token received ({log_id})",
            headers={"WWW-Authenticate": "Bearer",
            "set-cookie": response.headers["set-cookie"]},
        )
    elif share_request.request_logout:
        _clear_share_cookie(response, share_request.requested_target_token)
        return PvfShareAccessDenied_Base(failure_reason="session cleared"), None, None

    has_valid_cookie = view_token is not None and view_token == expected_cookie_token
    if not has_valid_cookie:
        _enforce_unauth_volume(request)

    shared_link_info = PvfShareLink.get_shared_link_by_id_or_magic_token_system(session=session,
                                                                             shared_magic_token=share_request.requested_target_token)
    if shared_link_info.failure_reason:
        log_event(f"Shared resource not available - {share_request.requested_target_token} - {shared_link_info.failure_reason}", severity=2,
                           usr_context=share_usr_context)
        _clear_share_cookie(response, share_request.requested_target_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Resource not available - {shared_link_info.failure_reason} ({shared_link_info.log_id})",
            headers={"WWW-Authenticate": "Bearer",
                     "set-cookie": response.headers.get("set-cookie", "")},
        )

    link_info = shared_link_info.link_info
    if link_info.shared_type != share_request.requested_target_share_type:
        log_event(f"Shared resource not available - requested access type does not match share - {link_info.shared_type} - {link_info.id}",
                           user_id=link_info.user_id, severity=3,
                           share_link_id=link_info.id,
                           usr_context=share_usr_context)
        _clear_share_cookie(response, share_request.requested_target_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Resource not available ({shared_link_info.log_id})",
            headers={"WWW-Authenticate": "Bearer",
                     "set-cookie": response.headers.get("set-cookie", "")},
        )

    user_info = PvfUser.get_user_by_id_system(session=session, id=link_info.user_id)
    if user_info is None or getattr(user_info, 'access_disabled', 0) > 1:
        log_event(f"Shared resource not available - originating user not active - {link_info.id}",
                           severity=2, share_link_id=link_info.id, usr_context=share_usr_context)
        _clear_share_cookie(response, share_request.requested_target_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Resource not available ({shared_link_info.log_id})",
            headers={"WWW-Authenticate": "Bearer",
                     "set-cookie": response.headers.get("set-cookie", "")},
        )

    shared_tags = []
    if link_info.shared_with_company_name not in (None, ""):
        shared_tags.append(link_info.shared_with_company_name)
    if link_info.shared_with_person_name not in (None, ""):
        shared_tags.append(link_info.shared_with_person_name)
    if link_info.shared_with_email not in (None, ""):
        shared_tags.append(link_info.shared_with_email)
    shared_with = ' - '.join(shared_tags)
    share_usr_context.sess_user = user_info
    share_usr_context.limited_proxy = True
    share_usr_context.sess_user.customer_admin = False
    share_usr_context.sess_user.power_user_mode = 0
    share_usr_context.sess_user.system_user_mode = 0
    share_usr_context.share_link_id = link_info.id
    share_usr_context.share_link_ident = shared_with

    access_denied_shell = PvfShareAccessDenied_Base()
    access_denied_shell.access_mode = link_info.access_mode
    if link_info.access_mode == PvfShareAccessCheckMode.email_any_unverified:
        access_denied_shell.verification_email_needed = True
    elif link_info.access_mode == PvfShareAccessCheckMode.email_any_verified:
        access_denied_shell.verification_email_needed = True
        access_denied_shell.verification_email_send_link_mode = True
    elif link_info.access_mode == PvfShareAccessCheckMode.email_matching:
        access_denied_shell.verification_email_needed = True
        access_denied_shell.verification_original_email_needed = True
    elif link_info.access_mode == PvfShareAccessCheckMode.email_matching_verified:
        access_denied_shell.verification_email_needed = True
        access_denied_shell.verification_original_email_needed = True
        access_denied_shell.verification_email_send_link_mode = True
    elif link_info.access_mode == PvfShareAccessCheckMode.recipient_email_verified:
        access_denied_shell.verification_email_send_link_mode = True
    elif link_info.access_mode == PvfShareAccessCheckMode.password_only:
        access_denied_shell.verification_password_needed = True
    elif link_info.access_mode == PvfShareAccessCheckMode.password_with_email_any_unverified:
        access_denied_shell.verification_password_needed = True
        access_denied_shell.verification_email_needed = True
    elif link_info.access_mode == PvfShareAccessCheckMode.password_with_email_any_verified:
        access_denied_shell.verification_password_needed = True
        access_denied_shell.verification_email_needed = True
        access_denied_shell.verification_email_send_link_mode = True
    elif link_info.access_mode == PvfShareAccessCheckMode.password_with_email_matching:
        access_denied_shell.verification_password_needed = True
        access_denied_shell.verification_email_needed = True
        access_denied_shell.verification_original_email_needed = True
    elif link_info.access_mode == PvfShareAccessCheckMode.password_with_email_matching_verified:
        access_denied_shell.verification_password_needed = True
        access_denied_shell.verification_email_needed = True
        access_denied_shell.verification_original_email_needed = True
        access_denied_shell.verification_email_send_link_mode = True
    elif link_info.access_mode == PvfShareAccessCheckMode.password_with_recipient_email_verified:
        access_denied_shell.verification_password_needed = True
        access_denied_shell.verification_email_send_link_mode = True
    elif link_info.access_mode == PvfShareAccessCheckMode.open_access:
        pass
    else:
        log_event(f"Unrecognized link share access mode {link_info.access_mode} - internal error",
                  severity=4, usr_context=share_usr_context, raise_exception=True)

    access_granted = None
    set_new_cookie = None
    if view_token == expected_cookie_token:
        access_granted = True

    magic_key_info = None

    if view_token is None and follow_up_use_existing_cookie_only:
        log_id = log_event(f"Attempting follow_up {share_request.requested_target_share_operation} operation without valid cookie token - {link_info.id}",
                           severity=2, share_link_id=link_info.id, usr_context=share_usr_context)
        _clear_share_cookie(response, share_request.requested_target_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Resource not available ({log_id})",
            headers={"WWW-Authenticate": "Bearer",
                     "set-cookie": response.headers.get("set-cookie", "")},
        )

    if share_request.verify_link_id is not None and share_request.verify_link_id != link_info.id:
        log_id = log_event(f"Attempting follow_up {share_request.requested_target_share_operation} operation with mismatched share link id - {link_info.id}",
                           severity=3, share_link_id=link_info.id, usr_context=share_usr_context)
        _clear_share_cookie(response, share_request.requested_target_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Resource not available ({log_id})",
            headers={"WWW-Authenticate": "Bearer",
                     "set-cookie": response.headers.get("set-cookie", "")},
        )

    if view_token is None and share_request.verification_magic_email_key not in (None, "", "string") and link_info.access_mode in (
        PvfShareAccessCheckMode.email_any_verified,
        PvfShareAccessCheckMode.email_matching_verified,
        PvfShareAccessCheckMode.recipient_email_verified,
        PvfShareAccessCheckMode.password_with_email_any_verified,
        PvfShareAccessCheckMode.password_with_email_matching_verified,
        PvfShareAccessCheckMode.password_with_recipient_email_verified,
    ):
        magic_key_info = PvfShareLinkMagicKey.get_shared_magic_key_record(session=session,
                                                                       usr_context=share_usr_context,
                                                                       shared_magic_token=share_request.requested_target_token,
                                                                       access_magic_key=share_request.verification_magic_email_key,
                                                                       clear_lock=False)

        if magic_key_info is not None:
            if magic_key_info.share_magic_token != share_request.requested_target_token:
                session.close()
                raise HTTPException(status_code=403, detail="Unexpected mismatch of share token and magic key")

            if magic_key_info.accessed_date is None:
                if magic_key_info.create_date + timedelta(minutes=settings.ACCESS_MAGIC_KEY_EXPIRATION_MINUTES) < datetime.now():
                    session.close()
                    access_denied_shell.verification_magic_link_expired = True
                    access_denied_shell.failure_reason = f'Magic login key expired after {settings.ACCESS_MAGIC_KEY_EXPIRATION_MINUTES} minutes'
                    access_granted = False
                else:
                    magic_key_info.set_shared_magic_key_record_used(session=session, usr_context=share_usr_context)
                    view_cookie_display_name = magic_key_info.captured_display_name
                    view_cookie_email = magic_key_info.captured_email
                    view_token, set_new_cookie = make_token_cookie(shared_magic_token=share_request.requested_target_token,
                                                                    display_name=magic_key_info.captured_display_name,
                                                                    email=magic_key_info.captured_email)
                    access_granted = True
            else:
                session.close()
                access_denied_shell.verification_magic_link_used = True
                access_denied_shell.failure_reason = 'Magic login key has already been used'
                access_granted = False
        else:
            access_denied_shell.verification_magic_link_incorrect = True
            access_denied_shell.failure_reason = 'Magic login key is not correct'
            access_granted = False

        if access_granted is False:
            _note_credential_failure(request, share_request.requested_target_token)
            return access_denied_shell, None, None

    if view_token is None and link_info.access_mode in (
        PvfShareAccessCheckMode.password_only,
        PvfShareAccessCheckMode.password_with_email_any_unverified,
        PvfShareAccessCheckMode.password_with_email_any_verified,
        PvfShareAccessCheckMode.password_with_email_matching,
        PvfShareAccessCheckMode.password_with_email_matching_verified,
        PvfShareAccessCheckMode.password_with_recipient_email_verified,
    ):
        if share_request.verification_password in (None, ""):
            access_denied_shell.verification_password_not_supplied = True
            access_granted = False
            access_denied_shell.failure_reason = 'Password not supplied'
        else:
            hashed_pw = get_hex_hash_from_args(settings.SHARE_LINK_REST_PW_HASH_KEY,
                                               link_info.magic_token,
                                               share_request.verification_password,
                                               settings.SHARE_LINK_REST_PW_HASH_KEY)
            if hashed_pw != link_info.share_password:
                access_granted = False
                access_denied_shell.verification_password_incorrect = True
                access_denied_shell.failure_reason = 'Password does not match'
        if access_granted is False:
            if access_denied_shell.verification_password_incorrect:
                _note_credential_failure(request, share_request.requested_target_token)
            return access_denied_shell, None, None

    if view_token is None:
        if link_info.access_mode in (PvfShareAccessCheckMode.open_access, PvfShareAccessCheckMode.password_only):
            access_granted = True
            view_token, set_new_cookie = make_token_cookie(shared_magic_token=share_request.requested_target_token,
                                                        display_name=share_request.display_name,
                                                        email=share_request.verification_email)
        elif link_info.access_mode in (
            PvfShareAccessCheckMode.email_any_unverified,
            PvfShareAccessCheckMode.password_with_email_any_unverified,
            PvfShareAccessCheckMode.email_matching,
            PvfShareAccessCheckMode.password_with_email_matching,
        ):
            if share_request.verification_email not in (None, ""):
                if link_info.access_mode in (PvfShareAccessCheckMode.email_matching, PvfShareAccessCheckMode.password_with_email_matching):
                    test_it = share_request.verification_email.lower() == (link_info.shared_with_email or "").lower()
                else:
                    test_it = re.search(r'[\w.]+\@[\w.]+', share_request.verification_email)
                if test_it:
                    access_granted = True
                    view_token, set_new_cookie = make_token_cookie(shared_magic_token=share_request.requested_target_token,
                                                                    display_name=share_request.display_name,
                                                                    email=share_request.verification_email)
                else:
                    if link_info.access_mode in (PvfShareAccessCheckMode.email_matching, PvfShareAccessCheckMode.password_with_email_matching):
                        access_denied_shell.failure_reason = 'Supplied email does not match email the link was shared with'
                    else:
                        access_denied_shell.failure_reason = 'Supplied email does not appear valid'
                    access_granted = False
                    _note_credential_failure(request, share_request.requested_target_token)
            else:
                access_denied_shell.verification_email_not_supplied = True
                access_denied_shell.failure_reason = 'An email address must be supplied'
        elif link_info.access_mode in (
            PvfShareAccessCheckMode.email_any_verified,
            PvfShareAccessCheckMode.password_with_email_any_verified,
            PvfShareAccessCheckMode.email_matching_verified,
            PvfShareAccessCheckMode.password_with_email_matching_verified,
            PvfShareAccessCheckMode.recipient_email_verified,
            PvfShareAccessCheckMode.password_with_recipient_email_verified,
        ):
            if link_info.access_mode not in (PvfShareAccessCheckMode.recipient_email_verified, PvfShareAccessCheckMode.password_with_recipient_email_verified):
                if share_request.verification_email not in (None, ""):
                    if link_info.access_mode in (PvfShareAccessCheckMode.email_matching_verified, PvfShareAccessCheckMode.password_with_email_matching_verified):
                        test_it = share_request.verification_email.lower() == (link_info.shared_with_email or "").lower()
                    else:
                        test_it = re.search(r'[\w.]+\@[\w.]+', share_request.verification_email)
                    if test_it and share_request.authorize_verification_email:
                        access_granted = False
                        key_info = PvfShareLinkMagicKey.create_shared_magic_key_record(session=session,
                                                                                    usr_context=share_usr_context,
                                                                                    share_link_id=link_info.id,
                                                                                    shared_magic_token=share_request.requested_target_token,
                                                                                    captured_display_name=share_request.display_name,
                                                                                    captured_email=share_request.verification_email,
                                                                                    original_link_recipient_email=link_info.shared_with_email,
                                                                                    )
                        email_result = send_outbound_mail(session=session,
                                                                usr_context=share_usr_context,
                                           email_type=PvfAuthRelatedOutboundEmailType.magic_access_key,
                                           destination_email=share_request.verification_email,
                                           email_params=dict(url_with_magic_key=build_share_landing_url(
                                                                 share_type=str(share_request.requested_target_share_type),
                                                                 magic_token=key_info.share_magic_token or "",
                                                                 access_magic_key=key_info.access_magic_key,
                                                             ),
                                                             url_prefix=external_base_url,
                                                             valid_duration=settings.ACCESS_MAGIC_KEY_EXPIRATION_MESSAGE,
                                                              url_suffix=external_suffix_url,
                                                              project_id=link_info.shared_entity_db_id,
                                                             project_name=link_info.share_link_name,
                                                              share_magic_token=key_info.share_magic_token,
                                                             access_magic_key=key_info.access_magic_key))
                        if email_result == "":
                            access_denied_shell.sent_magic_access_message = True
                            access_denied_shell.failure_reason = 'An access key has been sent to your email'
                        elif isinstance(email_result, str) and email_result.startswith("queued:"):
                            access_denied_shell.sent_magic_access_message = True
                            access_denied_shell.failure_reason = 'An access key has been queued for delivery to your email'
                        elif email_result not in (None, ""):
                            access_denied_shell.failure_reason = f'Unable to send access key email - {email_result}'
                    elif test_it and not share_request.authorize_verification_email:
                        access_denied_shell.failure_reason = 'Explicit authorization required to send a verification email'
                        access_granted = False
                    else:
                        access_denied_shell.failure_reason = 'Supplied email does not appear valid or is not an expected email address'
                        access_granted = False
                        _note_credential_failure(request, share_request.requested_target_token)
                else:
                    access_denied_shell.verification_email_not_supplied = True
                    access_denied_shell.failure_reason = 'An email address must be supplied'
            else:
                if share_request.verification_email not in (None, ""):
                    test_it = share_request.verification_email.lower() == (link_info.shared_with_email or "").lower()
                else:
                    test_it = True
                if test_it and share_request.authorize_verification_email:
                    access_granted = False
                    if share_request.verification_email not in (None, ""):
                        access_denied_shell.failure_reason = 'An access key has been sent to the email requested'
                    else:
                        access_denied_shell.failure_reason = 'An access key has been sent to the email on file'
                    access_denied_shell.sent_magic_access_message = True
                    key_info = PvfShareLinkMagicKey.create_shared_magic_key_record(session=session,
                                                                                usr_context=share_usr_context,
                                                                                share_link_id=link_info.id,
                                                                                shared_magic_token=share_request.requested_target_token,
                                                                                captured_display_name=share_request.display_name,
                                                                                captured_email=share_request.verification_email if share_request.verification_email not in (None, "") else "",
                                                                                original_link_recipient_email=link_info.shared_with_email,
                                                                                )
                    email_result = send_outbound_mail(session=session,
                                                            usr_context=share_usr_context,
                                    email_type=PvfAuthRelatedOutboundEmailType.magic_access_key,
                                    destination_email=link_info.shared_with_email,
                                    email_params=dict(
                                        url_with_magic_key=build_share_landing_url(
                                            share_type=str(share_request.requested_target_share_type),
                                            magic_token=key_info.share_magic_token or "",
                                            access_magic_key=key_info.access_magic_key,
                                        ),
                                                             url_prefix=external_base_url,
                                                              url_suffix=external_suffix_url,
                                                             valid_duration=settings.ACCESS_MAGIC_KEY_EXPIRATION_MESSAGE,
                                                              share_magic_token=key_info.share_magic_token,
                                                         access_magic_key=key_info.access_magic_key))
                    if email_result not in ("", None) and not (isinstance(email_result, str) and email_result.startswith("queued:")):
                        access_denied_shell.failure_reason = f'Unable to send email, possible anti-spam protections - {email_result}'
                elif test_it and not share_request.authorize_verification_email:
                    access_denied_shell.failure_reason = 'Explicit authorization required to send a verification email'
                    access_granted = False
                else:
                    access_denied_shell.failure_reason = 'The supplied email does not match the share request'
                    _note_credential_failure(request, share_request.requested_target_token)
        else:
            access_denied_shell.failure_reason = f"Unsupported access mode configuration {link_info.access_mode}"

    if not access_granted:
        return access_denied_shell, None, None

    if set_new_cookie is not None:
        response.set_cookie(settings.ACCESS_VIEW_COOKIE, set_new_cookie, httponly=True,
                            max_age=share_cookie_max_age_seconds(link_info.cookie_duration),
                            path=f"{settings.SHARE_WS_BASE_URL}{share_request.requested_target_token}/", samesite="strict", secure=_share_cookie_secure())
        if view_cookie_display_name is None:
            view_cookie_display_name = _normalize_cookie_field(share_request.display_name)
        if view_cookie_email is None:
            view_cookie_email = _normalize_cookie_field(share_request.verification_email)

    access_info = PvfShareLinkAccessed.create_or_increment_shared_link_access_record(session=session,
                                                                    usr_context=share_usr_context,
                                                                    share_link_info=link_info,
                                                                    cookie_value=view_token,
                                                                    captured_email=view_cookie_email,
                                                                    captured_display_name=view_cookie_display_name,
                                                                    )
    access_info.record_operation_used(session, share_request.requested_target_share_operation, clear_lock=False)

    result = PvfShareAccessConfirmed_Base(access_mode=link_info.access_mode,
                                        access_type=share_request.requested_target_share_type,
                                        access_operation=share_request.requested_target_share_operation,
                                        shared_entity_db_id=link_info.shared_entity_db_id,
                                        shared_entity_magic_token=link_info.magic_token or "",
                                        link_access_id=access_info.id,
                                        link_magic_key_id=magic_key_info.id if magic_key_info is not None else -1,
                                        link_access_count=access_info.access_count,
                                        share_id=link_info.id
                                        )

    if link_info.access_mode in (
        PvfShareAccessCheckMode.email_matching_verified,
        PvfShareAccessCheckMode.password_with_email_matching,
        PvfShareAccessCheckMode.password_with_email_matching_verified,
        PvfShareAccessCheckMode.recipient_email_verified,
        PvfShareAccessCheckMode.password_with_recipient_email_verified,
    ):
        result.viewer_organization_name = link_info.shared_with_company_name
        result.viewer_personal_name = link_info.shared_with_person_name
        result.viewer_captured_email = link_info.shared_with_email
    else:
        result.viewer_personal_name = view_cookie_display_name
        result.viewer_captured_email = view_cookie_email
    if link_info.access_mode in (
        PvfShareAccessCheckMode.email_matching_verified,
        PvfShareAccessCheckMode.password_with_email_matching_verified,
        PvfShareAccessCheckMode.recipient_email_verified,
        PvfShareAccessCheckMode.password_with_recipient_email_verified,
        PvfShareAccessCheckMode.email_any_verified,
        PvfShareAccessCheckMode.password_with_email_any_verified,
    ):
        result.is_email_verified = True

    return result, link_info, access_info


def _redact_share_link_for_response(share_row: PvfShareLink | None) -> tuple[PvfShareLink | None, bool]:
    """Return a response-safe detached PvfShareLink and whether a password is configured."""
    if share_row is None:
        return None, False
    password_set = bool(share_row.share_password)
    # Detach via dict so we never mutate a tracked ORM instance (session may be closed).
    data = share_row.model_dump()
    data["share_password"] = None
    return PvfShareLink.model_validate(data), password_set


def _finalize_share_activity_entry(
    entry: ShareLink_Auths_Accesses,
    extra_stats: dict[int, dict] | None = None,
    invite_by_token: dict[str, datetime] | None = None,
):
    keys = entry.share_link_magic_keys or []
    accesses = entry.share_link_accesses or []
    entry.magic_keys_issued = len(keys)
    entry.magic_keys_used = sum(1 for k in keys if k.accessed_date)
    entry.session_count = len(accesses)
    entry.total_hits = sum(int(a.access_count or 0) for a in accesses)
    if extra_stats and entry.share_id in extra_stats:
        for field_name, value in extra_stats[entry.share_id].items():
            setattr(entry, field_name, value)
    if entry.share_link is not None:
        token = entry.share_link.magic_token
        if token and invite_by_token and token in invite_by_token:
            entry.invite_email_sent = True
            entry.invite_email_last_sent = invite_by_token[token]
        entry.share_link_expired = _share_link_is_expired(entry.share_link)
        safe, password_set = _redact_share_link_for_response(entry.share_link)
        entry.share_link = safe
        entry.password_set = password_set
    return entry


@router.post('/get-share-activity-multiple-projects',
             summary="Return share activity for entities (or all)",
             tags=['share'])
def get_share_activity_multiple_projects(session: SessionDep, usr_context: UserAccessDep, project_id_list: list[int]) -> ShareActivityResultsMulti:
    if project_id_list is None or len(project_id_list) == 0 or (len(project_id_list) == 1 and project_id_list[0] in (0, -1)):
        project_id_list = None
    share_activity = PvfShareLink.get_shared_links_by_customer_id_and_project_ids(session=session, usr_context=usr_context, project_ids=project_id_list)
    if share_activity.failure_reason not in ("", None):
        return ShareActivityResultsMulti(failure_reason=share_activity.failure_reason, log_id=share_activity.log_id)
    if share_activity.link_info_list is None or len(share_activity.link_info_list) == 0:
        return ShareActivityResultsMulti(failure_reason="No matching share activity found")
    share_id_list = [cur_link.id for cur_link in share_activity.link_info_list]
    share_id_by_project_id = {cur_link.id: cur_link.shared_entity_db_id for cur_link in share_activity.link_info_list}
    key_gen_results = PvfShareLinkMagicKey.get_shared_magic_key_tracking_by_share_ids_system(session=session, usr_context=usr_context, share_ids=share_id_list)
    access_link_results = PvfShareLinkAccessed.get_shared_link_access_records_by_customer_id_and_project_ids_system(session=session, usr_context=usr_context, project_ids=project_id_list)
    share_info_result = ShareActivityResultsMulti()
    share_info_result.unknown_keys = []
    share_info_result.unknown_accesses = []

    hooks = get_hooks()
    extra_stats: dict[int, dict] = {}
    if share_id_list and hooks.share_activity_enricher is not None:
        extra_stats = hooks.share_activity_enricher(session=session, usr_context=usr_context, shares=share_activity.link_info_list) or {}
    invite_by_token = _latest_invite_send_by_token(
        session,
        usr_context.sess_user.customer_id,
        share_activity.link_info_list,
    )

    for cur_share_row in share_activity.link_info_list:
        share_url = build_share_landing_url(
            share_type=str(cur_share_row.shared_type),
            magic_token=cur_share_row.magic_token or "",
        )
        entry = ShareLink_Auths_Accesses(
            share_id=cur_share_row.id,
            project_id=cur_share_row.shared_entity_db_id,
            share_link=cur_share_row,
            share_link_url=share_url,
        )
        if cur_share_row.shared_entity_db_id not in share_info_result.share_info_list_per_project_id:
            share_info_result.share_info_list_per_project_id[cur_share_row.shared_entity_db_id] = [entry]
        else:
            share_info_result.share_info_list_per_project_id[cur_share_row.shared_entity_db_id].append(entry)

    if key_gen_results is not None:
        for cur_key_row in key_gen_results:
            if cur_key_row.share_id not in share_id_by_project_id:
                share_info_result.unknown_keys.append(cur_key_row)
                continue
            cur_project_id = share_id_by_project_id[cur_key_row.share_id]
            if cur_project_id not in share_info_result.share_info_list_per_project_id:
                share_info_result.share_info_list_per_project_id[cur_project_id] = [ShareLink_Auths_Accesses(share_id=cur_key_row.share_id,
                                                                                                              project_id=cur_project_id,
                                                                                                              share_link_magic_keys=[cur_key_row])]
            else:
                for cur_project_share in share_info_result.share_info_list_per_project_id[cur_project_id]:
                    if cur_project_share.share_id == cur_key_row.share_id:
                        cur_project_share.share_link_magic_keys.append(cur_key_row)
                        break
                else:
                    share_info_result.unknown_keys.append(cur_key_row)

    if access_link_results is not None:
        for cur_access_row in access_link_results:
            if cur_access_row.shared_entity_db_id not in share_info_result.share_info_list_per_project_id:
                share_info_result.share_info_list_per_project_id[cur_access_row.shared_entity_db_id] = [ShareLink_Auths_Accesses(share_id=cur_access_row.share_id, share_link_accesses=[cur_access_row])]
            else:
                for cur_project_share in share_info_result.share_info_list_per_project_id[cur_access_row.shared_entity_db_id]:
                    if cur_project_share.share_id == cur_access_row.share_id:
                        cur_project_share.share_link_accesses.append(cur_access_row)
                        break
                else:
                    share_info_result.unknown_accesses.append(cur_access_row)

    for project_entries in share_info_result.share_info_list_per_project_id.values():
        for entry in project_entries:
            _finalize_share_activity_entry(entry, extra_stats, invite_by_token)

    return share_info_result


@router.get('/get-share-activity-single-project',
             summary="Return share activity for a single entity",
             tags=['share'])
def get_share_activity_single_project(session: SessionDep, usr_context: UserAccessDep, project_id: int) -> ShareActivityResultsSingle:
    multi_results = get_share_activity_multiple_projects(session=session, usr_context=usr_context, project_id_list=[project_id])
    single_result = ShareActivityResultsSingle(failure_reason=multi_results.failure_reason, log_id=multi_results.log_id)
    single_result.unknown_keys = multi_results.unknown_keys
    single_result.unknown_accesses = multi_results.unknown_accesses
    if multi_results.share_info_list_per_project_id is not None and len(multi_results.share_info_list_per_project_id) > 0:
        returned_project_key = list(multi_results.share_info_list_per_project_id.keys())[0]
        single_result.share_info_list = multi_results.share_info_list_per_project_id[returned_project_key]
    return single_result
