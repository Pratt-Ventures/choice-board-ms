from __future__ import annotations

import threading
import time
from collections import OrderedDict
from copy import deepcopy
from typing import Any


_MAX_ENTRIES = 64
_LOCK = threading.Lock()
_CACHE: OrderedDict[str, tuple[float, dict]] = OrderedDict()


def cache_key(fingerprint: str, extra: str = "") -> str:
    return f"{fingerprint}:{extra}"


def get(key: str) -> tuple[dict | None, float | None]:
    now = time.monotonic()
    with _LOCK:
        hit = _CACHE.get(key)
        if not hit:
            return None, None
        _CACHE.move_to_end(key)
        stored_at, payload = hit
        return deepcopy(payload), (now - stored_at) * 1000.0


def put(key: str, payload: dict[str, Any]) -> None:
    with _LOCK:
        _CACHE[key] = (time.monotonic(), deepcopy(payload))
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX_ENTRIES:
            _CACHE.popitem(last=False)


def clear() -> None:
    with _LOCK:
        _CACHE.clear()


def size() -> int:
    with _LOCK:
        return len(_CACHE)
