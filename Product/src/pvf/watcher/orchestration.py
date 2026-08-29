"""Watcher orchestration types and capture/no-log helpers.

Status lifecycle: queued → trying → {complete | will_retry | no_retry | max_retries_exceeded}
with `failed` as terminal alias. PvfWatcherEventOrchestration mirrors PvfWebHookStatus but
adds will_retry/no_retry/max_retries_exceeded explicitly.

Capture policy (Q2): Single flag WATCHER_CAPTURE_PAYLOADS (default True). Logic:
  - If capture True and semantic_tag NOT in no_log union → persist full payloads
  - If capture False or tag in no_log → redact to {provider, model, prompt_hash, token_counts, latency_ms, status, semantic_tag}
  - no_log wins even on error.

Tenancy is enforced in bindings, not here; orchestration is framework-internal mapping.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field


class PvfWatcherStatus(str, Enum):
    queued = "queued"
    trying = "trying"
    complete = "complete"
    will_retry = "will_retry"
    no_retry = "no_retry"
    max_retries_exceeded = "max_retries_exceeded"
    failed = "failed"  # terminal alias (maps to no_retry or max_retries_exceeded)


# Alias for external consumers that expect PvfWebHookStatus-like naming
WatcherEventStatus = PvfWatcherStatus


class PvfWatcherEventOrchestration(BaseModel):
    """Per-attempt orchestration snapshot passed into each handler invocation."""
    status: str = Field(description="Current PvfWatcherStatus value")
    retries_remaining: int = Field(description="max_attempts - attempts")
    next_attempt_at: datetime | None = None
    is_no_log: bool = Field(default=False, description="True if semantic_tag in effective no_log union")


class PvfWatcherInvocation(BaseModel):
    """Invocation handed to each module.entry (detached row copy, no SA session)."""
    model_config = {"arbitrary_types_allowed": True}

    row: dict = Field(description="Detached copy of the queue row (model_dump)")
    customer_id: int | None = None
    user_id: int | None = None
    work_type: str = Field(description="Table-qualified work type: llm|outbound_email|outbound_api_call|<work_type>")
    semantic_tag: str | None = None
    request_package: dict = Field(default_factory=dict)
    attempt: int = Field(description="Current attempt number (1-based inside handler)")
    max_attempts: int = Field(description="Configured max_attempts for this row")
    orchestration: PvfWatcherEventOrchestration = Field(description="Status + retry + no_log snapshot")
    session_factory: Callable = Field(description="Callable to open a short session if handler needs DB reads")


class PvfWatcherInvocationResult(BaseModel):
    """PvfWsResultPackage-like return from each handler."""
    failure_reason: str = Field(default="", description='"" == success')
    result_package: dict | None = None
    error_package: dict | None = None
    retryable: bool | None = Field(default=None, description="None → framework decides; True/False overrides")
    next_delay_s: int | None = Field(default=None, description="Override retry_delays when not None")


# ---------------------------------------------------------------------------
# Capture / redaction helpers (unit-tested)
# ---------------------------------------------------------------------------

def _effective_no_log_set() -> set[str]:
    """Union of PvfGlobalSettings.WATCHER_NO_LOG_TYPES and PvfWatcherConfig.no_log_request_types."""
    from ..config.pvf_config_settings import pvf_settings
    from ..bindings.pvf_startup_config import load_watcher_config

    env_tags = set(getattr(pvf_settings, "WATCHER_NO_LOG_TYPES", []) or [])
    # watcher_config may be stored on settings by apply_watcher_config; else load fresh
    cfg = getattr(pvf_settings, "_watcher_config", None)
    if cfg is None:
        try:
            cfg = load_watcher_config()
        except Exception:
            cfg = None
    yaml_tags = set(getattr(cfg, "no_log_request_types", []) if cfg else [])
    return env_tags | yaml_tags


def is_no_log_tag(semantic_tag: str | None) -> bool:
    """True if semantic_tag is present in the effective no_log union."""
    if not semantic_tag:
        return False
    return semantic_tag in _effective_no_log_set()


def should_capture(semantic_tag: str | None) -> bool:
    """True if full payloads should be persisted for this tag."""
    from ..config.pvf_config_settings import pvf_settings

    capture = bool(getattr(pvf_settings, "WATCHER_CAPTURE_PAYLOADS", True))
    if not capture:
        return False
    return not is_no_log_tag(semantic_tag)


def redact_for_no_log(
    *,
    provider: str | None = None,
    model: str | None = None,
    prompt_hash: str | None = None,
    token_counts: dict | None = None,
    latency_ms: int | None = None,
    status: str | None = None,
    semantic_tag: str | None = None,
    error_code: str | None = None,
) -> dict:
    """Minimal redacted payload when capture is disabled or tag is no_log.

    On success: {provider, model, prompt_hash, token_counts, latency_ms, status, semantic_tag}
    On error (still suppressed when tag in no_log): same shape, no message/trace.
    """
    out: dict[str, Any] = {}
    if provider is not None:
        out["provider"] = provider
    if model is not None:
        out["model"] = model
    if prompt_hash is not None:
        out["prompt_hash"] = prompt_hash
    if token_counts is not None:
        out["token_counts"] = token_counts
    if latency_ms is not None:
        out["latency_ms"] = latency_ms
    if status is not None:
        out["status"] = status
    if semantic_tag is not None:
        out["semantic_tag"] = semantic_tag
    if error_code is not None:
        out["error_code"] = error_code
    return out


def prompt_hash_for_messages(prompt: str | None, messages: list | None) -> str | None:
    """Stable hash for prompt + messages (first 16 hex chars of sha256)."""
    if not prompt and not messages:
        return None
    h = hashlib.sha256()
    if prompt:
        h.update(str(prompt).encode("utf-8"))
    if messages:
        import json as _json
        try:
            h.update(_json.dumps(messages, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        except Exception:
            h.update(str(messages).encode("utf-8"))
    return h.hexdigest()[:16]
