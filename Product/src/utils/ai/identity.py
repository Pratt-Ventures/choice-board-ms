from __future__ import annotations

from typing import Any

from .config import is_default_model_key, normalize_model_key

AI_PARTICIPANT_KEY = "ai:default"
AI_DISPLAY_NAME = "AI AGENT: Default Model"
LEGACY_AI_PARTICIPANT_KEY = "ai:system"
LEGACY_AI_DISPLAY_NAME = "AI baseline"


def build_ai_participant_key(model_key: str | None = None) -> str:
    if is_default_model_key(model_key):
        return AI_PARTICIPANT_KEY
    return "ai:" + normalize_model_key(model_key)


def ai_display_name(model_key: str | None = None, *, resolved_model: str | None = None) -> str:
    if is_default_model_key(model_key):
        return AI_DISPLAY_NAME
    label = str(resolved_model or model_key or "").strip() or "Unknown"
    return f"AI AGENT: {label}"


def _as_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(getattr(item, "__dict__", {}) or {})


def is_ai_source(value: Any) -> bool:
    if value is None:
        return False
    raw = getattr(value, "value", value)
    return str(raw).strip().lower() == "ai"


def is_ai_participant(row: Any) -> bool:
    d = _as_dict(row)
    if bool(d.get("is_ai") if isinstance(d, dict) else getattr(row, "is_ai", False)):
        return True
    if is_ai_source(d.get("source") if isinstance(d, dict) else getattr(row, "source", None)):
        return True
    key = str(d.get("participant_key") if isinstance(d, dict) else getattr(row, "participant_key", None) or "")
    return key == AI_PARTICIPANT_KEY or key == LEGACY_AI_PARTICIPANT_KEY or key.startswith("ai:")


def _row_id(row: Any, field: str) -> int | None:
    d = _as_dict(row)
    raw = d.get(field) if isinstance(d, dict) else getattr(row, field, None)
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    return v if v else None


def partition_vote_data(
    participants: list | None,
    groups: list | None,
) -> tuple[list, list, list, list]:
    human_parts: list = []
    ai_parts: list = []
    ai_pids: set[int] = set()
    for p in participants or []:
        if is_ai_participant(p):
            ai_parts.append(p)
            pid = _row_id(p, "id")
            if pid:
                ai_pids.add(pid)
        else:
            human_parts.append(p)
    human_groups: list = []
    ai_groups: list = []
    for g in groups or []:
        pid = _row_id(g, "participant_id")
        if pid is not None and pid in ai_pids:
            ai_groups.append(g)
        else:
            human_groups.append(g)
    return human_parts, human_groups, ai_parts, ai_groups


def participant_is_complete(row: Any) -> bool:
    d = _as_dict(row)
    return bool(d.get("is_complete") if isinstance(d, dict) else getattr(row, "is_complete", False))
