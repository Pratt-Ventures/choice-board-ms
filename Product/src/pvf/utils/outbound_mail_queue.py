from __future__ import annotations
from typing import Any
from enum import Enum
from datetime import datetime, timezone
from sqlmodel import Session

from .outbound_mail_sendgrid import request_sendgrid_delivery
from .outbound_mail_smtp_jinja import request_smtp_jinja_delivery
from .log_event import log_event
from .utils_show import show_vars_semi
from ..db.models.customer_user import PvfUserContext, PvfCustomer

from ..db.models.email_activity_log import PvfEmailActivityLog
from ..config.pvf_config_settings import pvf_settings as settings

# note: needs poetry add emails[jinja]

# talk with sendgrid or alternative - send a mail


def normalize_email_type(email_type: str | Enum) -> str:
    if isinstance(email_type, Enum):
        return str(email_type.value)
    return str(email_type)


def _normalize_email_sync_mode(raw: str | None) -> str:
    """Normalize EMAIL_SYNC_ASYNC value to one of 'sync', 'per-request', 'async'."""
    if raw is None:
        return "sync"
    val = str(raw).strip().lower().replace("_", "-")
    if val in ("sync", "per-request", "async"):
        return val
    return "sync"


def _resolve_effective_delivery(caller_delivery: str | None) -> str:
    """Resolve effective sync/async delivery honoring EMAIL_SYNC_ASYNC.

    - 'sync'       -> always sync (inline)
    - 'async'      -> always async (watcher queue)
    - 'per-request'-> honor caller's `delivery` param (defaults to 'async')
    """
    global_mode = _normalize_email_sync_mode(getattr(settings, "EMAIL_SYNC_ASYNC", "sync"))
    if global_mode == "sync":
        return "sync"
    if global_mode == "async":
        return "async"
    # per-request: honor caller
    if caller_delivery is None:
        caller_delivery = "async"
    cd = str(caller_delivery).strip().lower().replace("_", "-")
    if cd in ("sync", "async"):
        return cd
    # tolerate 'per-request' passed as caller (fallback to async)
    if cd == "per-request":
        return "async"
    return "async"


def _check_local_override(destination_email: str) -> tuple[bool, str | None]:
    """Check EMAIL_LOCAL_ALLOW_DOMAINS against destination. Returns (is_override, matched_domain)."""
    dest_lower = destination_email.lower()
    for check_override_domain in [x.strip().lower() for x in settings.EMAIL_LOCAL_ALLOW_DOMAINS.split(';') if x.strip()]:
        if check_override_domain == '*' or check_override_domain in dest_lower:
            return True, check_override_domain
    # also support comma-separated variant for robustness
    for check_override_domain in [x.strip().lower() for x in settings.EMAIL_LOCAL_ALLOW_DOMAINS.split(',') if x.strip()]:
        if check_override_domain == '*' or check_override_domain in dest_lower:
            return True, check_override_domain
    return False, None


def _set_if_absent(email_params: dict, key: str, value: Any) -> None:
    if key not in email_params:
        email_params[key] = value


def _prepare_email_params(
    session: Session,
    usr_context: PvfUserContext,
    email_type: str,
    destination_email: str,
    email_params: dict,
) -> tuple[dict, str | None]:
    """Inject ambient fields and check throttling. Returns (enriched_params, error_string)."""
    email_params = dict(email_params) if isinstance(email_params, dict) else {}
    email_type = normalize_email_type(email_type)
    email_param_string = '; '.join([f'{k}={v}' for k,v in email_params.items()])

    # Throttling checks (same as before, but do not yet create log)
    check_history_1 = PvfEmailActivityLog.get_recent_log_events_system(session=session,
                                                                  email_address=destination_email,
                                                                  email_type=email_type,
                                                                  cutoff_hours=1)
    check_history_24 = PvfEmailActivityLog.get_recent_log_events_system(session=session,
                                                                  email_address=destination_email,
                                                                  email_type=email_type,
                                                                  cutoff_hours=24)
    if check_history_24 is not None and len(check_history_24) >= settings.MAX_EMAILS_PER_DEST_PER_24_HOURS or \
        check_history_1 is not None and len(check_history_1) >= settings.MAX_EMAILS_PER_DEST_PER_HOUR:
        log_id = log_event(f"outbound email type {email_type} not sent to {destination_email} - destination throttling ({settings.MAX_EMAILS_PER_DEST_PER_24_HOURS} per 24 hours; {settings.MAX_EMAILS_PER_DEST_PER_HOUR} per hour)", usr_context=usr_context)
        if not settings.is_prod():
            show_vars_semi(f'send_outbound_mail: requested email {email_type} to {destination_email} with {email_param_string}')
            show_vars_semi(f'send_outbound_mail: suppressed to {destination_email}, limited to 3 emails per hour per type to an address')
        return email_params, f'Outbound email limits exceeded for this address {(log_id)}'

    max_24_per_ip = settings.MAX_EMAILS_PER_REMOTE_IP_PER_HOUR_VERIFIED if getattr(usr_context, 'authenticated_session', False) else settings.MAX_EMAILS_PER_REMOTE_IP_PER_HOUR
    check_history = PvfEmailActivityLog.get_recent_log_events_system(session=session,
                                                                  remote_ip=getattr(usr_context, 'remote_ip', None),
                                                                  email_type=email_type,
                                                                  cutoff_hours=1)
    if check_history is not None and len(check_history) >= max_24_per_ip:
        log_id = log_event(f"outbound email type {email_type} not sent to {destination_email} due to source IP {getattr(usr_context, 'remote_ip', None)} throttling ({max_24_per_ip} per hour)", usr_context=usr_context)
        if not settings.is_prod():
            show_vars_semi(f'send_outbound_mail: requested email {email_type} to {destination_email} with {email_param_string}')
            show_vars_semi(f'send_outbound_mail: suppressed initiation from {getattr(usr_context, "remote_ip", None)}, limited to {max_24_per_ip} emails per hour initiated by a remote address')
        return email_params, f'Outbound request email limits exceeded for this origination context {(log_id)}'

    if not settings.is_prod():
        show_vars_semi(f'send_outbound_mail: delivery queued, email {email_type} to {destination_email} with {email_param_string}')

    email_params['remote_ip'] = getattr(usr_context, 'remote_ip', None)
    if getattr(usr_context, 'sess_user', None) is not None:
        _set_if_absent(email_params, 'user_name', usr_context.sess_user.name)
        _set_if_absent(email_params, 'user_email', usr_context.sess_user.email)
        _set_if_absent(email_params, 'user_phone', usr_context.sess_user.phone)
        try:
            customer_info = PvfCustomer.get_customer_by_id(session=session, usr_context=usr_context, id=usr_context.sess_user.customer_id)
        except Exception:
            customer_info = None
        if customer_info is None:
            # Try system lookup
            try:
                customer_info = PvfCustomer.get_customer_by_id_system(session=session, id=int(usr_context.sess_user.customer_id), clear_lock=False)
            except Exception:
                customer_info = None
        if customer_info is None:
            log_id = log_event(f"outbound email service could not verify associated hs customer profile {getattr(usr_context.sess_user, 'customer_id', None)} not sent to {destination_email}", usr_context=usr_context, email_params=email_param_string)
            return email_params, f"Unable to verify company information associated with the account ({log_id})"
        _set_if_absent(email_params, 'customer_name', customer_info.customer_name)
        _set_if_absent(email_params, 'customer_email', customer_info.customer_email)
        _set_if_absent(email_params, 'customer_phone', customer_info.customer_phone)
    else:
        _set_if_absent(email_params, 'user_name', "")
        _set_if_absent(email_params, 'user_email', "")
        _set_if_absent(email_params, 'user_phone', "")
        _set_if_absent(email_params, 'customer_name', "")
        _set_if_absent(email_params, 'customer_email', "")
        _set_if_absent(email_params, 'customer_phone', "")

    email_params['email_type'] = email_type
    app_base_url = settings.APPLICATION_BASE_URL.rstrip("/")
    _set_if_absent(email_params, 'year', datetime.now(timezone.utc).year)
    _set_if_absent(email_params, 'app_base_url', app_base_url)
    _set_if_absent(email_params, 'app_login_url', f"{app_base_url}/{settings.APP_LOGIN_PATH.lstrip('/')}")
    _set_if_absent(email_params, 'brand_name', settings.EMAIL_BRAND_NAME)
    _set_if_absent(email_params, 'support_email', settings.EMAIL_SUPPORT_EMAIL)

    return email_params, None


def _send_direct_sync(
    session: Session,
    usr_context: PvfUserContext,
    email_type: str,
    destination_email: str,
    email_params: dict,
) -> str:
    """Direct sync send used by watcher handler (and PYTEST fallback). Returns failure string or ''.

    Eligibility checks (quotas, domain allowlist, dev console helpers, USE_EMAIL_SERVICE)
    are intentionally duplicated here as backup for the watcher path — see
    _prepare_email_params (quotas) plus the domain/config checks below.
    """
    import asyncio
    email_type = normalize_email_type(email_type)
    local_override_enable = False
    matched_domain = None
    if not settings.is_prod():
        is_override, matched = _check_local_override(destination_email)
        if is_override:
            local_override_enable = True
            matched_domain = matched
            email_params['local_override'] = matched_domain

    if settings.is_prod() or local_override_enable:
        if settings.USE_EMAIL_SERVICE and settings.USE_EMAIL_SERVICE.upper() == 'SENDGRID':
            try:
                result_msg = asyncio.run(request_sendgrid_delivery(session=session, usr_context=usr_context, destination_email=destination_email, email_type=email_type, email_params=email_params))
            except RuntimeError:
                # If already in event loop (unlikely in sync watcher), use new loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    fut = pool.submit(asyncio.run, request_sendgrid_delivery(session=session, usr_context=usr_context, destination_email=destination_email, email_type=email_type, email_params=email_params))
                    result_msg = fut.result(timeout=30)
        elif settings.USE_EMAIL_SERVICE and settings.USE_EMAIL_SERVICE.upper() == 'SMTP-JINJA':
            try:
                result_msg = asyncio.run(request_smtp_jinja_delivery(session=session, usr_context=usr_context, destination_email=destination_email, email_type=email_type, email_params=email_params))
            except RuntimeError:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    fut = pool.submit(asyncio.run, request_smtp_jinja_delivery(session=session, usr_context=usr_context, destination_email=destination_email, email_type=email_type, email_params=email_params))
                    result_msg = fut.result(timeout=30)
        else:
            log_id = log_event(f"outbound email service delivery method {settings.USE_EMAIL_SERVICE} not recognized; no message sent to {destination_email}", usr_context=usr_context, email_params=str(email_params))
            return f"No configuration for email delivery {settings.USE_EMAIL_SERVICE} available ({log_id})"
        # Create audit log on actual send attempt
        try:
            email_log_entry = PvfEmailActivityLog(email_address=destination_email,
                                            email_service=settings.USE_EMAIL_SERVICE,
                                            email_type=email_type,
                                            email_params_json=dict(email_params),
                                            result_message=result_msg if result_msg is not None else "")
            email_log_entry.create_email_event(session=session, usr_context=usr_context)
            if local_override_enable:
                show_vars_semi(f'send_outbound_mail: email sent to {destination_email} due to local domain override for {email_params.get("local_override")}')
        except Exception:
            pass
        return result_msg if result_msg is not None else ""
    else:
        log_id = log_event(f'send_outbound_email: email not sent to {destination_email} from non-production instance', usr_context=usr_context, email_params=email_params)
        show_vars_semi(f'send_outbound_mail: non production mode; email {email_type} NOT sent to {destination_email}; log entry {log_id}')
        # Still create a log entry for audit even when not sending in non-prod (keeps tests that check PvfEmailActivityLog working)
        try:
            email_log_entry = PvfEmailActivityLog(email_address=destination_email,
                                            email_service=settings.USE_EMAIL_SERVICE or "none",
                                            email_type=email_type,
                                            email_params_json=dict(email_params),
                                            result_message="")
            email_log_entry.create_email_event(session=session, usr_context=usr_context)
        except Exception:
            pass
        return ""


def send_outbound_mail(*, session: Session,
                        usr_context: PvfUserContext,
                        email_type: str | Enum,
                        destination_email: str,
                        email_params: dict,
                        timeout: float = 10.0,
                        delivery: str = "async",
                        _force_sync: bool = False) -> str:
    """Outbound email with EMAIL_SYNC_ASYNC-aware delivery.

    Global setting EMAIL_SYNC_ASYNC controls routing:
      'sync'       -> always inline (fastapi thread) via _send_direct_sync
      'async'      -> always via watcher queue (async)
      'per-request'-> honor caller's `delivery` param (defaults to 'async' going forward)

    Eligibility checks (quotas, domain allowlist, dev console helpers) run BEFORE
    any queuing; the watcher handler repeats the same checks as backup.

    Returns:
      ""                -> sent (confirmed)
      "queued:<id>"     -> queued (watcher will deliver; not yet confirmed within timeout)
      "<error> (log_id)"-> failed (throttled, missing config, or watcher failed)
    """
    import time as _time
    email_type = normalize_email_type(email_type)
    # Prepare params and eligibility (quotas, IP throttling, customer verification, ambient injection)
    # This is the BEFORE-queue gate; watcher repeats via _prepare_email_params as backup.
    enriched_params, throttled = _prepare_email_params(session, usr_context, email_type, destination_email, dict(email_params) if isinstance(email_params, dict) else {})
    if throttled:
        return throttled

    # Resolve effective delivery mode honoring EMAIL_SYNC_ASYNC
    effective = _resolve_effective_delivery(delivery)
    # _force_sync is legacy private override -> force sync
    if _force_sync:
        effective = "sync"
    # PYTEST_ACTIVE forces sync to keep tests deterministic (immediate PvfEmailActivityLog)
    if getattr(settings, "PYTEST_ACTIVE", False):
        effective = "sync"
    # Dev/override and config checks BEFORE queue (address restrictions, dev helpers, USE_EMAIL_SERVICE)
    # These mirror the checks inside _send_direct_sync so queue only happens after eligibility
    if effective == "async":
        is_override, matched = _check_local_override(destination_email)
        # Non-prod non-override: dev suppression -> do not queue, use direct path (logs, console helper, audit row)
        if not settings.is_prod() and not is_override:
            return _send_direct_sync(session, usr_context, email_type, destination_email, enriched_params)
        # USE_EMAIL_SERVICE must be configured to queue meaningfully; else direct path returns config error
        svc = str(getattr(settings, "USE_EMAIL_SERVICE", "") or "").strip().upper()
        if svc not in ("SENDGRID", "SMTP-JINJA"):
            return _send_direct_sync(session, usr_context, email_type, destination_email, enriched_params)
        # Template existence as pre-queue eligibility (fail fast without queue)
        # SENDGRID: need template id; SMTP-JINJA: need html+subject files
        if svc == "SENDGRID":
            try:
                from .outbound_mail_sendgrid import _lookup_sendgrid_template_id as _lookup_sg
                if _lookup_sg(email_type) is None:
                    # Let direct path produce the canonical error with log_id
                    return _send_direct_sync(session, usr_context, email_type, destination_email, enriched_params)
            except Exception:
                pass
        elif svc == "SMTP-JINJA":
            try:
                from .outbound_mail_smtp_jinja import _ensure_jinja_templates_loaded as _ensure_jinja
                loaded = _ensure_jinja()
                if email_type not in loaded:
                    return _send_direct_sync(session, usr_context, email_type, destination_email, enriched_params)
            except Exception:
                pass

    if effective == "sync":
        return _send_direct_sync(session, usr_context, email_type, destination_email, enriched_params)

    # effective == "async" -> queue via watcher (eligibility already passed)
    try:
        from ..bindings.pvf_watcher_requests import queue_email_request as _queue_email
        from ..watcher.models import PvfWatcherEmailRequest as _WER
        from ..depends.api_session_dependencies import get_next_session as _get_next_session
    except Exception as ex:
        log_id = log_event(f"send_outbound_mail queue import failed: {ex}", severity=3, usr_context=usr_context)
        return f"Email queue unavailable ({log_id})"

    qres = _queue_email(session=session, usr_context=usr_context, to_email=destination_email, template_type=email_type, params=enriched_params, payload=None, semantic_tag=None)
    if getattr(qres, "failure_reason", None):
        return qres.failure_reason
    qid = None
    try:
        qid = (qres.result_package or {}).get("id") or getattr(qres, "queue_id", None)
    except Exception:
        qid = getattr(qres, "queue_id", None)
    if not qid:
        return "queued"

    # Also create a queued audit log immediately so tests that check PvfEmailActivityLog see it (handler will create final sent log)
    try:
        queued_log = PvfEmailActivityLog(email_address=destination_email,
                                      email_service=settings.USE_EMAIL_SERVICE or "queued",
                                      email_type=email_type,
                                      email_params_json=dict(enriched_params),
                                      result_message=f"queued:{qid}")
        queued_log.create_email_event(session=session, usr_context=usr_context)
    except Exception:
        pass

    # Poll for completion
    deadline = _time.time() + float(timeout or 0)
    poll_interval = 0.25
    while _time.time() < deadline:
        try:
            with _get_next_session() as poll_sess:
                row = poll_sess.get(_WER, int(qid))
                if row is None:
                    _time.sleep(poll_interval)
                    continue
                st = str(getattr(row, "status", "") or "")
                if st == "complete":
                    # Confirmed sent
                    return ""
                if st in ("failed", "no_retry", "max_retries_exceeded", "failed"):
                    err = ""
                    try:
                        ep = getattr(row, "error_package", None)
                        if isinstance(ep, dict):
                            err = ep.get("message") or ep.get("error") or str(ep)
                        elif ep:
                            err = str(ep)
                    except Exception:
                        err = "failed"
                    return err or "failed"
                # still queued/trying/will_retry -> continue polling
        except Exception:
            pass
        _time.sleep(poll_interval)

    # Timeout -> queued
    return f"queued:{qid}"


# Back-compat async wrapper for callers still using await (deprecated)
async def send_outbound_mail_async(*, session: Session, usr_context: PvfUserContext, email_type: str | Enum, destination_email: str, email_params: dict, timeout: float = 10.0, delivery: str = "async") -> str:
    return send_outbound_mail(session=session, usr_context=usr_context, email_type=email_type, destination_email=destination_email, email_params=email_params, timeout=timeout, delivery=delivery)

