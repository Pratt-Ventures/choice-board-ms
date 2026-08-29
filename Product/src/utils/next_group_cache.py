"""In-process cache of issued sort groups (pending client completion)."""
from __future__ import annotations

import time
from typing import Any

_TTL_SECONDS = 300.0
_CACHE: dict[str, tuple[float, dict]] = {}


def _key(scope: str, project_id: int, participant_id: int) -> str:
    return f"{scope}:{int(project_id)}:{int(participant_id)}"


def get_issued_group(*, scope: str, project_id: int, participant_id: int) -> dict | None:
    k = _key(scope, project_id, participant_id)
    hit = _CACHE.get(k)
    if not hit:
        return None
    exp, payload = hit
    if time.time() > exp:
        _CACHE.pop(k, None)
        return None
    return dict(payload)


def set_issued_group(
    *,
    scope: str,
    project_id: int,
    participant_id: int,
    group: dict | None,
) -> None:
    k = _key(scope, project_id, participant_id)
    if not group:
        _CACHE.pop(k, None)
        return
    _CACHE[k] = (time.time() + _TTL_SECONDS, dict(group))


def invalidate_participant(*, scope: str, project_id: int, participant_id: int) -> None:
    _CACHE.pop(_key(scope, project_id, participant_id), None)


# Back-compat no-ops for any lingering imports
def get_prepared_group(**_kwargs) -> Any:
    return None


def set_prepared_group(**_kwargs) -> None:
    return None


def observation_state_fingerprint(*_a, **_k) -> str:
    return ""
