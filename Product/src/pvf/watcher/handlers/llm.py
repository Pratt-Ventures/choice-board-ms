"""LLM watcher handler — wraps pvf.utils.llm_client.query_llm_model.

Retries 3 times by default (AI_HTTP_RETRIES), honors LlmError.retryable,
and respects WATCHER_CAPTURE_PAYLOADS + tag suppression before persisting.

Entry: handle_llm(inv: PvfWatcherInvocation) -> PvfWatcherInvocationResult
"""
from __future__ import annotations

import time
from typing import Any

from ...utils.llm_client import LlmError, query_llm_model
from ...utils.field_encryption import decrypt_secret
from ..orchestration import PvfWatcherInvocationResult, should_capture, is_no_log_tag, prompt_hash_for_messages


def _compute_prompt_bytes(prompt: str | None, messages: list | None) -> int | None:
    import json
    try:
        if messages is not None:
            return len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))
        if prompt is not None:
            return len(str(prompt).encode("utf-8"))
    except Exception:
        try:
            return len(str(prompt or "").encode("utf-8"))
        except Exception:
            return None
    return None


def _compute_response_bytes(text: str | None, session_contents: dict | None) -> int | None:
    import json
    try:
        if text is not None:
            b = len(str(text).encode("utf-8"))
            # Also include raw trace size if present for total
            if isinstance(session_contents, dict):
                try:
                    raw = session_contents.get("response")
                    if raw is not None:
                        raw_b = len(json.dumps(raw, ensure_ascii=False).encode("utf-8"))
                        return max(b, raw_b)
                except Exception:
                    pass
            return b
        if isinstance(session_contents, dict):
            return len(json.dumps(session_contents, ensure_ascii=False).encode("utf-8"))
    except Exception:
        return None
    return None


def handle_llm(inv) -> PvfWatcherInvocationResult:
    """Framework builtin LLM handler with fallback and byte diagnostics."""
    row = inv.row or {}
    # Provider/model/api_key from row or request_package
    req = inv.request_package or {}
    provider = row.get("provider") or req.get("provider") or "opencode_go"
    model = row.get("model") or req.get("model") or ""
    api_key_enc = row.get("api_key_encrypted")
    api_key = decrypt_secret(api_key_enc) if api_key_enc else req.get("api_key")
    key_source = row.get("key_source") or req.get("key_source")

    # Fallback if api_key still missing: resolve via customer/system at handler time
    if not api_key:
        customer_id = row.get("customer_id") or req.get("customer_id")
        if not customer_id:
            customer_id = inv.customer_id
        if customer_id:
            try:
                with inv.session_factory() as _sess:
                    from ...db.models.customer_user import PvfCustomer as _Cust
                    from ...utils.field_encryption import decrypt_secret as _dec
                    cust = _sess.get(_Cust, int(customer_id))
                    if cust is not None:
                        enc = getattr(cust, "ai_api_key", None)
                        dec = _dec(enc) if enc else ""
                        dec = str(dec or "").strip()
                        prov_c = str(getattr(cust, "ai_provider", "") or "").strip()
                        if prov_c and dec:
                            api_key = dec
                            key_source = key_source or "pvf_customer"
                            if not provider or provider == "opencode_go":
                                provider = prov_c
                            if not model:
                                model = str(getattr(cust, "ai_model", "") or "").strip()
            except Exception:
                pass
        if not api_key:
            try:
                from ...config.pvf_config_settings import pvf_settings as _ps
                sys_key = str(getattr(_ps, "AI_API_KEY", "") or "").strip()
                if sys_key and sys_key.lower() not in ("", "specify in .env", "<specify>", "changeme"):
                    api_key = sys_key
                    key_source = key_source or "system"
                    if not provider:
                        provider = str(getattr(_ps, "AI_SERVICE", "") or "").strip() or "opencode_go"
                    if not model:
                        model = str(getattr(_ps, "AI_MODEL", "") or "").strip()
            except Exception:
                pass

    # Messages / prompt
    messages = row.get("messages_json") or req.get("messages")
    prompt = req.get("prompt") or row.get("prompt") or ""
    # Temperature / max_tokens from request_package
    temperature = req.get("temperature", 0.2)
    max_tokens = req.get("max_tokens", 800)
    if temperature is None:
        temperature = 0.2
    if max_tokens is None:
        max_tokens = 800

    # If messages still None and prompt present, let llm_client build messages
    # Honor capture gating: should_capture already decided at queue time, but handler also respects it
    start = time.time()
    try:
        session_contents, text = query_llm_model(
            prompt or "",
            provider=provider,
            model=model or None,
            api_key=api_key or None,
            messages=messages,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )
        latency_ms = int((time.time() - start) * 1000)
        prompt_bytes = _compute_prompt_bytes(prompt, messages)
        response_bytes = _compute_response_bytes(text, session_contents)
        # Persist bytes and key_source back to row (via result_package + direct row update if possible)
        try:
            # Update DB row bytes if we have access to session_factory
            with inv.session_factory() as _sess2:
                from ...watcher.models import PvfWatcherLlmRequest as _WLR
                _row = _sess2.get(_WLR, row.get("id"))
                if _row is not None:
                    if prompt_bytes is not None:
                        _row.prompt_bytes = prompt_bytes
                    if response_bytes is not None:
                        _row.response_bytes = response_bytes
                    if key_source and not getattr(_row, "key_source", None):
                        _row.key_source = key_source
                    _sess2.add(_row)
                    _sess2.commit()
        except Exception:
            pass
        # Build result_package — only include raw_trace when capture allowed
        capture = should_capture(inv.semantic_tag)
        if capture and not is_no_log_tag(inv.semantic_tag):
            result_pkg = {
                "text": text,
                "session_contents": session_contents,
                "latency_ms": latency_ms,
                "provider": provider,
                "model": model,
                "semantic_tag": inv.semantic_tag,
                "key_source": key_source,
                "prompt_bytes": prompt_bytes,
                "response_bytes": response_bytes,
                "raw_trace": session_contents.get("response") if isinstance(session_contents, dict) else None,
            }
            # Extract usage if present in response
            try:
                resp = session_contents.get("response") if isinstance(session_contents, dict) else None
                if isinstance(resp, dict) and "usage" in resp:
                    result_pkg["usage"] = resp["usage"]
            except Exception:
                pass
        else:
            # Redacted — no text trace, no messages
            phash = prompt_hash_for_messages(prompt, messages)
            result_pkg = {
                "provider": provider,
                "model": model,
                "prompt_hash": phash,
                "latency_ms": latency_ms,
                "status": "complete",
                "semantic_tag": inv.semantic_tag,
                "key_source": key_source,
                "prompt_bytes": prompt_bytes,
                "response_bytes": response_bytes,
            }
        return PvfWatcherInvocationResult(
            failure_reason="",
            result_package=result_pkg,
            error_package=None,
            retryable=None,
        )
    except LlmError as ex:
        latency_ms = int((time.time() - start) * 1000)
        # Map LlmError.retryable to framework retry semantics
        msg = str(ex) or "LLM error"
        retryable = bool(getattr(ex, "retryable", False))
        return PvfWatcherInvocationResult(
            failure_reason=msg,
            result_package=None,
            error_package={"code": type(ex).__name__, "message": msg, "retryable": retryable, "latency_ms": latency_ms},
            retryable=retryable,
        )
    except Exception as ex:
        msg = f"{type(ex).__name__}: {ex}"
        return PvfWatcherInvocationResult(
            failure_reason=msg,
            result_package=None,
            error_package={"code": type(ex).__name__, "message": str(ex), "retryable": False},
            retryable=False,
        )
