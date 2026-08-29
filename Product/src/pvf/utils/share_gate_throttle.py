"""In-process sliding-window throttle for unauthenticated share-gate attempts."""
from __future__ import annotations

import threading
import time

from ..config.pvf_config_settings import pvf_settings as settings

_lock = threading.Lock()
_hits: dict[str, list[float]] = {}

_UNAUTH_PREFIX = "unauth-ip:"
_FAIL_IP_PREFIX = "fail-ip:"
_FAIL_TOKEN_PREFIX = "fail-token:"


def _window() -> float:
    return float(getattr(settings, "SHARE_GATE_THROTTLE_WINDOW_SECONDS", 3600) or 3600)


def _prune(times: list[float], now: float, window: float) -> list[float]:
    cutoff = now - window
    return [t for t in times if t > cutoff]


def reset_share_gate_throttle() -> None:
    with _lock:
        _hits.clear()


def _record(key: str) -> int:
    now = time.monotonic()
    window = _window()
    with _lock:
        times = _prune(_hits.get(key) or [], now, window)
        times.append(now)
        _hits[key] = times
        return len(times)


def _count(key: str) -> int:
    now = time.monotonic()
    window = _window()
    with _lock:
        times = _prune(_hits.get(key) or [], now, window)
        if times:
            _hits[key] = times
        else:
            _hits.pop(key, None)
        return len(times)


def record_unauth_hit(remote_ip: str | None) -> int:
    ip = (remote_ip or "").strip() or "unknown"
    return _record(f"{_UNAUTH_PREFIX}{ip}")


def record_credential_failure(remote_ip: str | None, magic_token: str | None) -> tuple[int, int]:
    ip = (remote_ip or "").strip() or "unknown"
    token = (magic_token or "").strip() or "unknown"
    ip_count = _record(f"{_FAIL_IP_PREFIX}{ip}")
    token_count = _record(f"{_FAIL_TOKEN_PREFIX}{ip}:{token}")
    return ip_count, token_count


def unauth_volume_exceeded(remote_ip: str | None) -> bool:
    limit = int(getattr(settings, "SHARE_GATE_MAX_UNAUTH_PER_IP_PER_HOUR", 0) or 0)
    if limit <= 0:
        return False
    ip = (remote_ip or "").strip() or "unknown"
    return _count(f"{_UNAUTH_PREFIX}{ip}") >= limit


def credential_failure_exceeded(remote_ip: str | None, magic_token: str | None) -> bool:
    ip_limit = int(getattr(settings, "SHARE_GATE_MAX_FAILURES_PER_IP_PER_HOUR", 0) or 0)
    token_limit = int(getattr(settings, "SHARE_GATE_MAX_FAILURES_PER_TOKEN_PER_HOUR", 0) or 0)
    ip = (remote_ip or "").strip() or "unknown"
    token = (magic_token or "").strip() or "unknown"
    if ip_limit > 0 and _count(f"{_FAIL_IP_PREFIX}{ip}") >= ip_limit:
        return True
    if token_limit > 0 and _count(f"{_FAIL_TOKEN_PREFIX}{ip}:{token}") >= token_limit:
        return True
    return False
