"""Generic poll_and_dispatch — replaces itertools.cycle in powerchoice_watcher.py:71.

Per-type claim: SELECT … FOR UPDATE SKIP LOCKED LIMIT 1 ordered by next_attempt_at, id
where status='queued' and next_attempt_at <= now() (or NULL).

Then bumps queued → trying, calls handler(PvfWatcherInvocation) -> PvfWatcherInvocationResult,
maps to complete | will_retry (next_attempt_at=now+delay) | no_retry | max_retries_exceeded.

Respects WATCHER_CAPTURE_PAYLOADS + no_log tag filtering before persisting result/raw_trace.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from ..config.pvf_config_settings import pvf_settings
from .orchestration import (
    PvfWatcherInvocation,
    PvfWatcherEventOrchestration,
    PvfWatcherInvocationResult,
    PvfWatcherStatus,
    is_no_log_tag,
    prompt_hash_for_messages,
    redact_for_no_log,
    should_capture,
)
from .registry import PvfWatcherRegistry

logger = logging.getLogger(__name__)

# Default retry delays (seconds) per queue type when handler returns retryable True without next_delay_s
_RETRY_DELAYS = {
    "llm": [1, 4, 10],
    "outbound_email": [1, 4, 10, 60, 60],
    "outbound_api_call": [1, 4, 10, 60, 60, 120, 120],
    "generic": [1, 4, 10, 60],
}


def _delay_for_attempt(work_type: str, attempt: int, override: int | None = None) -> int:
    if override is not None:
        return int(override)
    delays = _RETRY_DELAYS.get(work_type, _RETRY_DELAYS["generic"])
    idx = min(max(0, attempt - 1), len(delays) - 1)
    return int(delays[idx])


def _is_dialect_postgres(session: Session) -> bool:
    try:
        return "postgres" in str(session.get_bind().dialect.name).lower() or "postgresql" in str(session.get_bind().url)
    except Exception:
        try:
            return "postgres" in pvf_settings.DB_PATH_OR_CONNECTION_STRING.lower()
        except Exception:
            return False


def _claim_row(session: Session, table_cls, *, work_type_filter: str | None = None) -> Any | None:
    """Claim one row via FOR UPDATE SKIP LOCKED when possible, else plain SELECT."""
    from sqlalchemy import and_

    now = datetime.now()
    # Build base query: queued and next_attempt_at <= now or NULL
    q = select(table_cls).where(
        table_cls.status == PvfWatcherStatus.queued.value,
    )
    # next_attempt_at eligibility
    # SQLite stores NULL without index; treat NULL as eligible immediately
    q = q.where(
        (table_cls.next_attempt_at.is_(None)) | (table_cls.next_attempt_at <= now)
    )
    if work_type_filter is not None and hasattr(table_cls, "work_type"):
        q = q.where(table_cls.work_type == work_type_filter)
    q = q.order_by(table_cls.next_attempt_at.asc().nullsfirst(), table_cls.id.asc()).limit(1)

    is_pg = _is_dialect_postgres(session)
    if is_pg:
        q = q.with_for_update(skip_locked=True)

    row = session.exec(q).one_or_none()
    if row is None:
        return None
    # Bump to trying
    row.status = PvfWatcherStatus.trying.value
    row.attempts = int(getattr(row, "attempts", 0) or 0) + 1
    # Leave next_attempt_at as-is until handler decides
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _finalize_row(
    session: Session,
    row,
    result: PvfWatcherInvocationResult,
    *,
    work_type: str,
    semantic_tag: str | None,
) -> str:
    """Map PvfWatcherInvocationResult to terminal status, respecting capture/no-log."""
    capture = should_capture(semantic_tag)
    # Extract retryable intent
    retryable = result.retryable
    if retryable is None and result.error_package is not None:
        retryable = bool(result.error_package.get("retryable")) if isinstance(result.error_package, dict) else False
    # Determine if error_package indicates retryable when failure_reason present
    if result.failure_reason and retryable is None:
        retryable = False

    attempts = int(getattr(row, "attempts", 0) or 0)
    max_attempts = int(getattr(row, "max_attempts", 3) or 3)

    # Decide terminal status
    is_success = not result.failure_reason
    if is_success:
        new_status = PvfWatcherStatus.complete.value
        # Persist bytes/key_source for LLM if present in result_package
        if isinstance(result.result_package, dict):
            if hasattr(row, "prompt_bytes") and result.result_package.get("prompt_bytes") is not None:
                try:
                    row.prompt_bytes = int(result.result_package.get("prompt_bytes"))
                except Exception:
                    pass
            if hasattr(row, "response_bytes") and result.result_package.get("response_bytes") is not None:
                try:
                    row.response_bytes = int(result.result_package.get("response_bytes"))
                except Exception:
                    pass
            if hasattr(row, "key_source") and result.result_package.get("key_source") and not getattr(row, "key_source", None):
                row.key_source = str(result.result_package.get("key_source"))
        # Persist result
        if capture:
            row.result_package = result.result_package
            if hasattr(row, "raw_trace") and result.result_package and isinstance(result.result_package, dict):
                # For LLM, raw_trace mirrors response body when captured
                row.raw_trace = result.result_package.get("raw_trace") or result.result_package.get("response") or result.result_package
            row.error_package = None
        else:
            # Redacted: only minimal fields
            prov = getattr(row, "provider", None)
            mdl = getattr(row, "model", None)
            phash = getattr(row, "prompt_hash", None)
            # Try to derive token_counts/latency from result_package
            token_counts = None
            latency_ms = None
            if isinstance(result.result_package, dict):
                token_counts = result.result_package.get("usage") or result.result_package.get("token_counts")
                latency_ms = result.result_package.get("latency_ms")
            row.result_package = redact_for_no_log(provider=prov, model=mdl, prompt_hash=phash, token_counts=token_counts, latency_ms=latency_ms, status=new_status, semantic_tag=semantic_tag)
            # Preserve diagnostics even when redacted
            if isinstance(result.result_package, dict):
                if result.result_package.get("prompt_bytes") is not None:
                    row.result_package["prompt_bytes"] = result.result_package.get("prompt_bytes")
                if result.result_package.get("response_bytes") is not None:
                    row.result_package["response_bytes"] = result.result_package.get("response_bytes")
                if result.result_package.get("key_source") is not None:
                    row.result_package["key_source"] = result.result_package.get("key_source")
            row.error_package = None
            if hasattr(row, "messages_json"):
                row.messages_json = None
            if hasattr(row, "raw_trace"):
                row.raw_trace = None
        row.completed_at = datetime.now()
    else:
        # Failure path — no_log wins even on error
        if is_no_log_tag(semantic_tag):
            # Still suppress — store redacted error
            if capture:
                # Need to decide: spec says no_log suppresses even on error when tag in no_log_request_types
                # So force redacted even if capture True
                capture = False
        if retryable is True and attempts < max_attempts:
            new_status = PvfWatcherStatus.will_retry.value
            delay = _delay_for_attempt(work_type, attempts, result.next_delay_s)
            row.next_attempt_at = datetime.now() + timedelta(seconds=delay)
            # Persist error (respect capture)
            if capture:
                row.error_package = result.error_package or {"message": result.failure_reason, "retryable": True}
                row.result_package = result.result_package
            else:
                row.error_package = redact_for_no_log(status=new_status, semantic_tag=semantic_tag, error_code=result.error_package.get("code") if isinstance(result.error_package, dict) else None) if isinstance(result.error_package, dict) else {"status": new_status}
                row.result_package = None
            # Flip back to queued for retry (will_retry is transient → queued with next_attempt_at)
            # Spec says will_retry = requeue with retries_remaining-1; we model as queued with future next_attempt_at
            new_status = PvfWatcherStatus.queued.value
        elif retryable is True and attempts >= max_attempts:
            new_status = PvfWatcherStatus.max_retries_exceeded.value
            row.next_attempt_at = None
            row.completed_at = datetime.now()
            if capture:
                row.error_package = result.error_package or {"message": result.failure_reason, "retryable": True}
            else:
                row.error_package = redact_for_no_log(status=new_status, semantic_tag=semantic_tag)
        else:
            # retryable is False or None without retry
            new_status = PvfWatcherStatus.no_retry.value
            row.next_attempt_at = None
            row.completed_at = datetime.now()
            if capture:
                row.error_package = result.error_package or {"message": result.failure_reason}
            else:
                row.error_package = redact_for_no_log(status=new_status, semantic_tag=semantic_tag)
            # failed alias maps to no_retry; keep explicit
        row.status = new_status
        # For will_retry path we already set queued; for others set terminal
        if new_status not in (PvfWatcherStatus.queued.value,):
            row.status = new_status
        else:
            row.status = PvfWatcherStatus.queued.value
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.status

    row.status = new_status
    session.add(row)
    session.commit()
    session.refresh(row)
    return new_status


def _build_invocation(row, *, work_type: str, table_name: str) -> PvfWatcherInvocation:
    sem_tag = getattr(row, "semantic_tag", None)
    req_pkg = getattr(row, "request_package", None) or {}
    if not isinstance(req_pkg, dict):
        req_pkg = {"request_package": req_pkg}
    customer_id = getattr(row, "customer_id", None)
    user_id = getattr(row, "created_by_user_id", None)
    attempts = int(getattr(row, "attempts", 0) or 0)
    max_attempts = int(getattr(row, "max_attempts", 3) or 3)
    is_no_log = is_no_log_tag(sem_tag)
    # Callable factory for handler to open short session if it needs DB reads
    def _session_factory():
        from ..depends.api_session_dependencies import get_next_session
        return get_next_session()

    return PvfWatcherInvocation(
        row=row.model_dump() if hasattr(row, "model_dump") else dict(row.__dict__),
        customer_id=customer_id,
        user_id=user_id,
        work_type=work_type,
        semantic_tag=sem_tag,
        request_package=req_pkg,
        attempt=attempts,
        max_attempts=max_attempts,
        orchestration=PvfWatcherEventOrchestration(
            status=getattr(row, "status", PvfWatcherStatus.trying.value),
            retries_remaining=max(0, max_attempts - attempts),
            next_attempt_at=getattr(row, "next_attempt_at", None),
            is_no_log=is_no_log,
        ),
        session_factory=_session_factory,
    )


def poll_and_dispatch(session: Session, registry: PvfWatcherRegistry) -> bool:
    """Poll all bound types and dispatch one unit of work.

    Returns True if any work was dispatched (caller should reset idle_count),
    False if idle.
    """
    from ..watcher.models import PvfWatcherLlmRequest, PvfWatcherEmailRequest, PvfWatcherApiRequest, PvfWatcherGenericJob

    # Order: dedicated types first (llm, outbound_email, outbound_api_call), then generic work_types
    # Registry ordering is YAML order (insertion order); fall back to canonical order
    type_order = list(registry.all_types()) if registry and registry.all_types() else ["llm", "outbound_email", "outbound_api_call"]

    # Map work_type → table + handler work_type key
    table_map: dict[str, Any] = {
        "llm": PvfWatcherLlmRequest,
        "outbound_email": PvfWatcherEmailRequest,
        "outbound_api_call": PvfWatcherApiRequest,
    }

    # Try dedicated tables
    for wt in type_order:
        table_cls = table_map.get(wt)
        if table_cls is None:
            # Could be app generic type — will be handled via generic table scan below
            continue
        handler = registry.resolve_handler(wt) if registry else None
        if handler is None:
            # No handler registered for this builtin — skip but still claim? No, skip
            continue
        row = _claim_row(session, table_cls)
        if row is None:
            continue
        inv = _build_invocation(row, work_type=wt, table_name=table_cls.__tablename__)
        try:
            result = handler(inv)
            if not isinstance(result, PvfWatcherInvocationResult):
                # Coerce legacy string return (callback_delivery style)
                if isinstance(result, str):
                    if result in ("", None):
                        result = PvfWatcherInvocationResult(failure_reason="", result_package={"message": "ok"})
                    else:
                        result = PvfWatcherInvocationResult(failure_reason=str(result), error_package={"message": str(result)}, retryable=False)
                elif result is None:
                    result = PvfWatcherInvocationResult(failure_reason="")
                else:
                    result = PvfWatcherInvocationResult(failure_reason="", result_package={"result": result})
        except Exception as ex:
            logger.exception("watcher handler %r raised", wt)
            result = PvfWatcherInvocationResult(failure_reason=f"{type(ex).__name__}: {ex}", error_package={"message": str(ex), "retryable": False}, retryable=False)
        _finalize_row(session, row, result, work_type=wt, semantic_tag=getattr(row, "semantic_tag", None))
        return True

    # Generic table: each distinct work_type that has a handler, plus fallback polling
    # First, poll work_types with registered handlers
    generic_handlers = [(wt, h) for wt, h in (registry.entries.items() if registry else []) if wt not in table_map]
    for wt, entry in generic_handlers:
        handler = registry.resolve_handler(wt) if registry else None
        if handler is None:
            continue
        row = _claim_row(session, PvfWatcherGenericJob, work_type_filter=wt)
        if row is None:
            continue
        inv = _build_invocation(row, work_type=wt, table_name=PvfWatcherGenericJob.__tablename__)
        try:
            result = handler(inv)
            if not isinstance(result, PvfWatcherInvocationResult):
                if isinstance(result, str):
                    result = PvfWatcherInvocationResult(failure_reason=str(result) if result else "", error_package={"message": str(result)} if result else None, retryable=False if result else None)
                elif result is None:
                    result = PvfWatcherInvocationResult(failure_reason="")
                else:
                    result = PvfWatcherInvocationResult(failure_reason="", result_package={"result": result})
        except Exception as ex:
            logger.exception("watcher generic handler %r raised", wt)
            result = PvfWatcherInvocationResult(failure_reason=f"{type(ex).__name__}: {ex}", error_package={"message": str(ex), "retryable": False}, retryable=False)
        _finalize_row(session, row, result, work_type=wt, semantic_tag=getattr(row, "semantic_tag", None))
        return True

    # Fallback: any generic job whose work_type has no registered handler but is queued
    # We still attempt to dispatch via generic handler if registry has a wildcard, or just leave it pending
    # For now, try to claim any generic row (oldest) even if no handler — will mark no_retry
    fallback_row = _claim_row(session, PvfWatcherGenericJob)
    if fallback_row is not None:
        wt = getattr(fallback_row, "work_type", "generic")
        handler = registry.resolve_handler(wt) if registry else None
        if handler is None:
            # No handler — mark no_retry
            result = PvfWatcherInvocationResult(failure_reason=f"no handler registered for work_type {wt!r}", error_package={"message": f"no handler for {wt}", "retryable": False}, retryable=False)
        else:
            inv = _build_invocation(fallback_row, work_type=wt, table_name=PvfWatcherGenericJob.__tablename__)
            try:
                result = handler(inv)
                if not isinstance(result, PvfWatcherInvocationResult):
                    result = PvfWatcherInvocationResult(failure_reason="" if not result else str(result))
            except Exception as ex:
                result = PvfWatcherInvocationResult(failure_reason=f"{type(ex).__name__}: {ex}", error_package={"message": str(ex), "retryable": False}, retryable=False)
        _finalize_row(session, fallback_row, result, work_type=wt, semantic_tag=getattr(fallback_row, "semantic_tag", None))
        return True

    return False

# Back-compat alias for earlier doc naming
poll_once = poll_and_dispatch
