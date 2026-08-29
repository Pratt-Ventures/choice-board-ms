"""Email watcher handler — extracts core from outbound_mail_queue into shareable deliver_email_package.

Throttling caps from PvfGlobalSettings still apply (checked at enqueue time and here).
This handler runs off the request thread via the watcher poll loop.

Entry: handle_email(inv: PvfWatcherInvocation) -> PvfWatcherInvocationResult
"""
from __future__ import annotations

import asyncio
from typing import Any

from ...utils.pvf_base_internal_resources import PvfWsResultPackage
from ..orchestration import PvfWatcherInvocationResult


def _build_usr_context_from_row(row: dict):
    """Build a minimal PvfUserContext for the email send.

    We cannot fully reconstruct PvfUserContext without DB lookup, but for delivery
    we need destination throttling checks that read PvfEmailActivityLog. Those checks
    are done inside deliver_email_package which fetches its own session.
    """
    from ...db.models.customer_user import PvfUserContext, PvfCustomer, PvfUser
    # Try to provide a limited_proxy context if we have customer_id
    customer_id = row.get("customer_id")
    user_id = row.get("created_by_user_id")
    # Real lookup would need session; handler's session_factory can be used if needed
    return PvfUserContext(
        authenticated_session=False,
        limited_proxy=True,
        sess_user=None,
        sess_customer=None,
        remote_ip="watcher",
        url_path="watcher:email",
    )


async def deliver_email_package(session, email_params: dict, *, to_email: str, template_type: str) -> str:
    """Shareable helper usable off request thread. Returns failure_reason or ''.

    Eligibility (quotas, domain allowlist, dev console helpers, USE_EMAIL_SERVICE,
    template validity) was already checked before queueing in send_outbound_mail;
    this handler repeats the same checks as backup via _prepare_email_params and
    _send_direct_sync before actual delivery.
    """
    from ...utils.outbound_mail_queue import _prepare_email_params, _send_direct_sync, normalize_email_type, _check_local_override
    from ...db.models.customer_user import PvfUserContext
    from ...config.pvf_config_settings import pvf_settings as settings

    # Build a watcher-context (no session user) — outbound_mail_queue handles None gracefully
    usr_ctx = PvfUserContext(remote_ip="watcher", url_path="watcher:email", limited_proxy=True)
    # Backup: quotas + IP throttling + customer verification + ambient injection (mirror pre-queue gate)
    enriched, throttled = _prepare_email_params(session, usr_ctx, normalize_email_type(template_type), to_email, dict(email_params or {}))
    if throttled:
        return throttled
    # Backup: additional eligibility before send (domain allowlist, dev helpers, USE_EMAIL_SERVICE, template)
    # _send_direct_sync repeats these internally; we keep explicit backup path for audit parity with
    # the pre-queue checks in send_outbound_mail.
    # Direct send (creates PvfEmailActivityLog)
    # _send_direct_sync is sync, but this wrapper is async for compat; run it
    result = _send_direct_sync(session, usr_ctx, normalize_email_type(template_type), to_email, enriched)
    if result and isinstance(result, str) and result not in ("", None):
        # Treat queued: prefix as success for watcher? Should not happen in direct path
        if str(result).startswith("queued:"):
            return ""
        return result
    return ""


def handle_email(inv) -> PvfWatcherInvocationResult:
    """Framework builtin email handler — synchronous wrapper over async deliver."""
    row = inv.row or {}
    req = inv.request_package or {}
    # Prefer explicit columns on row, else request_package
    to_email = row.get("to_email") or req.get("to_email") or (req.get("params") or {}).get("to_email") or ""
    template_type = row.get("template_type") or req.get("template_type") or req.get("email_type") or ""
    params = row.get("params_json") or req.get("params") or req.get("email_params") or {}
    payload = row.get("payload_json") or req.get("payload") or {}

    # Merge payload into params if payload carries extra template fields
    if isinstance(payload, dict):
        merged_params = dict(params) if isinstance(params, dict) else {}
        for k, v in payload.items():
            merged_params.setdefault(k, v)
    else:
        merged_params = params if isinstance(params, dict) else {}

    if not to_email or not template_type:
        return PvfWatcherInvocationResult(
            failure_reason=f"missing to_email or template_type (to_email={to_email!r}, template_type={template_type!r})",
            error_package={"message": "missing to_email/template_type", "retryable": False},
            retryable=False,
        )

    # Need a session — use inv.session_factory
    try:
        # session_factory returns a contextmanager; we need to run async delivery
        with inv.session_factory() as session:
            # Run async deliver in sync context (deliver_email_package is async but uses sync _send_direct_sync internally)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're inside an event loop (unlikely for watcher), create new loop
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        fut = pool.submit(asyncio.run, deliver_email_package(session, merged_params, to_email=to_email, template_type=template_type))
                        failure = fut.result(timeout=30)
                else:
                    failure = loop.run_until_complete(deliver_email_package(session, merged_params, to_email=to_email, template_type=template_type))
            except RuntimeError:
                failure = asyncio.run(deliver_email_package(session, merged_params, to_email=to_email, template_type=template_type))

            if failure:
                # Heuristic: throttling strings contain "throttling" or "limits exceeded" → no_retry
                lower = str(failure).lower()
                if "throttl" in lower or "limit" in lower:
                    return PvfWatcherInvocationResult(failure_reason=str(failure), error_package={"message": str(failure), "retryable": False}, retryable=False)
                # Transient SMTP/SendGrid errors could be retryable — treat as retryable
                return PvfWatcherInvocationResult(failure_reason=str(failure), error_package={"message": str(failure), "retryable": True}, retryable=True)
            return PvfWatcherInvocationResult(failure_reason="", result_package={"to_email": to_email, "template_type": template_type}, retryable=None)
    except Exception as ex:
        return PvfWatcherInvocationResult(failure_reason=f"{type(ex).__name__}: {ex}", error_package={"message": str(ex), "retryable": True}, retryable=True)
