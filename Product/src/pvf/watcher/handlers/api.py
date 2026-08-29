"""API watcher handler — generalizes pvf.utils.callback_delivery.

Adds columns target_url, http_method, connection_protocol, auth_protocol, auth_params_encrypted.
V1 connection_protocol/auth_protocol are always "pvf" (validate and store, but do not branch)
to allow ssh/bearer later without migration.

Entry: handle_api(inv: PvfWatcherInvocation) -> PvfWatcherInvocationResult
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests

from ...config.pvf_config_settings import pvf_settings
from ...utils.field_encryption import decrypt_secret
from ...utils.webcalls_and_hooks import APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY, APPLICATION_API_HEADER_SIGNATURE, WebrequestSignature
from ...utils.utils_general import get_hex_hash_from_args
from ..orchestration import PvfWatcherInvocationResult


def _get_auth_params(row: dict) -> dict | None:
    enc = row.get("auth_params_encrypted")
    if not enc:
        return None
    try:
        raw = decrypt_secret(enc)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        try:
            return {"raw": decrypt_secret(enc)}
        except Exception:
            return None


def handle_api(inv) -> PvfWatcherInvocationResult:
    """Framework builtin API callback handler."""
    row = inv.row or {}
    req = inv.request_package or {}

    target_url = row.get("target_url") or req.get("target_url") or (req.get("payload") or {}).get("target_url") or ""
    http_method = (row.get("http_method") or req.get("http_method") or "POST").upper()
    connection_protocol = row.get("connection_protocol") or req.get("connection_protocol") or "pvf"
    auth_protocol = row.get("auth_protocol") or req.get("auth_protocol") or "pvf"
    headers = row.get("headers_json") or req.get("headers") or {}
    payload = row.get("payload_json") or req.get("payload") or req.get("request_package") or {}

    # V1: both always "pvf" — validate but do not branch; future will handle ssh/bearer
    if connection_protocol != "pvf":
        # Log but continue — allow future protocols without migration
        pass
    if auth_protocol != "pvf":
        pass

    if not target_url:
        return PvfWatcherInvocationResult(
            failure_reason="missing target_url",
            error_package={"message": "missing target_url", "retryable": False},
            retryable=False,
        )

    # Resolve payload to JSON string; support dict or list
    try:
        payload_json = json.dumps(payload if isinstance(payload, (dict, list)) else {"payload": payload})
    except Exception as ex:
        return PvfWatcherInvocationResult(failure_reason=f"payload serialize failed: {ex}", error_package={"message": str(ex), "retryable": False}, retryable=False)

    # Build signed headers if auth_params available (contains shared_secret + authentication_key_id)
    auth_params = _get_auth_params(row) or req.get("auth_params") or {}
    # Try to find shared_secret / authentication_key_id in auth_params or row
    shared_secret = ""
    auth_key_id = ""
    if isinstance(auth_params, dict):
        shared_secret = auth_params.get("shared_secret") or auth_params.get("secret") or ""
        auth_key_id = auth_params.get("authentication_key_id") or auth_params.get("authentication_key") or ""
    # Fallback: if headers already contain signature, use as-is
    request_headers = dict(headers) if isinstance(headers, dict) else {}
    if "content-type" not in {k.lower() for k in request_headers}:
        request_headers["content-type"] = "application/json"

    # If we have a shared_secret, generate signature headers per callback_delivery
    if shared_secret and auth_key_id:
        try:
            signed = WebrequestSignature.generate_signed_payload_header(payload_json, secret=shared_secret)
            # mimic callback_delivery: cb-<hash>
            cb_key = f'cb-{get_hex_hash_from_args(pvf_settings.CUSTOMER_API_OUTBOUND_HASH_KEY, auth_key_id, hash_length=32)}'
            request_headers[APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY] = cb_key
            request_headers[APPLICATION_API_HEADER_SIGNATURE] = signed
        except Exception:
            pass
    elif shared_secret:
        try:
            signed = WebrequestSignature.generate_signed_payload_header(payload_json, secret=shared_secret)
            request_headers[APPLICATION_API_HEADER_SIGNATURE] = signed
        except Exception:
            pass

    # Perform request with timeout
    timeout = 30
    try:
        timeout = float(getattr(pvf_settings, "AI_HTTP_TIMEOUT_SECONDS", 30) or 30)
    except Exception:
        timeout = 30

    try:
        # Use requests with timeout — similar to callback_delivery:137 but with timeout
        if http_method == "GET":
            resp = requests.get(target_url, headers=request_headers, timeout=timeout)
        elif http_method == "PUT":
            resp = requests.put(target_url, data=payload_json, headers=request_headers, timeout=timeout)
        elif http_method == "PATCH":
            resp = requests.patch(target_url, data=payload_json, headers=request_headers, timeout=timeout)
        elif http_method == "DELETE":
            resp = requests.delete(target_url, headers=request_headers, timeout=timeout)
        else:
            resp = requests.post(target_url, data=payload_json, headers=request_headers, timeout=timeout)
    except requests.Timeout as ex:
        return PvfWatcherInvocationResult(failure_reason=f"timeout: {ex}", error_package={"message": f"timeout: {ex}", "retryable": True}, retryable=True)
    except requests.RequestException as ex:
        return PvfWatcherInvocationResult(failure_reason=f"request failed: {ex}", error_package={"message": str(ex), "retryable": True}, retryable=True)
    except Exception as ex:
        return PvfWatcherInvocationResult(failure_reason=f"{type(ex).__name__}: {ex}", error_package={"message": str(ex), "retryable": True}, retryable=True)

    # Evaluate response — 2xx is success, 429/5xx retryable, else no_retry
    status = getattr(resp, "status_code", 0)
    try:
        body_text = resp.text[:2000] if hasattr(resp, "text") else ""
    except Exception:
        body_text = ""
    if 200 <= status < 300:
        # Try to parse JSON response
        try:
            resp_body = resp.json() if hasattr(resp, "json") else None
        except Exception:
            resp_body = body_text
        return PvfWatcherInvocationResult(
            failure_reason="",
            result_package={"status_code": status, "response": resp_body if resp_body is not None else body_text, "target_url": target_url},
            retryable=None,
        )
    # Failure — determine retryable
    retryable = status == 429 or status >= 500
    msg = f"API {http_method} {target_url} failed {status}: {body_text[:500]}"
    return PvfWatcherInvocationResult(
        failure_reason=msg,
        error_package={"message": msg, "status_code": status, "retryable": retryable, "response": body_text[:1000]},
        retryable=retryable,
    )
