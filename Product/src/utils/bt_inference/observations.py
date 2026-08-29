from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SOFT_EXCLUDE = frozenset({"unsure", "skip", "skipped"})
USABLE = frozenset({"winner", "tie"})


def _as_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(getattr(item, "__dict__", {}) or {})


def _status_value(g: dict) -> str:
    status = g.get("status")
    if hasattr(status, "value"):
        status = status.value
    return str(status or "")


def _group_type(g: dict) -> str:
    gt = g.get("group_type") or g.get("type") or "alternative"
    if hasattr(gt, "value"):
        gt = gt.value
    return str(gt)


def _int_or_none(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class PairObs:
    participant_id: int
    channel: str
    factor_id: int | None
    winner_id: int
    loser_id: int
    y: float
    left_sign: float
    group_key: str
    seq: int
    response: str
    legacy: bool


def _group_key(g: dict, fallback: int) -> str:
    for k in ("id", "group_token", "client_group_id"):
        v = g.get(k)
        if v is not None and str(v):
            return str(v)
    return f"anon:{fallback}"


def _left_sign(winner_id: int, loser_id: int, pairing: dict) -> float:
    left = pairing.get("presented_left_id")
    if left is None:
        left = pairing.get("presentedLeftId")
    lid = _int_or_none(left)
    if lid is None:
        return 0.0
    if lid == int(winner_id):
        return 1.0
    if lid == int(loser_id):
        return -1.0
    return 0.0


def _usable_pairing(raw: Any) -> PairObs | None:
    if not isinstance(raw, dict):
        return None
    resp = raw.get("response") or "winner"
    if hasattr(resp, "value"):
        resp = resp.value
    resp = str(resp).lower()
    if resp in SOFT_EXCLUDE:
        return None
    if resp not in USABLE:
        if raw.get("winner_id") is not None and raw.get("loser_id") is not None:
            resp = "winner"
        else:
            return None
    try:
        w = int(raw["winner_id"])
        l = int(raw["loser_id"])
    except (TypeError, ValueError, KeyError):
        return None
    if w == l:
        return None
    y = 0.5 if resp == "tie" else 1.0
    return PairObs(
        participant_id=0,
        channel="",
        factor_id=None,
        winner_id=w,
        loser_id=l,
        y=y,
        left_sign=_left_sign(w, l, raw),
        group_key="",
        seq=0,
        response=resp,
        legacy=False,
    )


def _adjacent_from_rank_order(order: list) -> list[tuple[int, int]]:
    ids: list[int] = []
    for x in order or []:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            continue
    out = []
    for a, b in zip(ids, ids[1:]):
        if a != b:
            out.append((a, b))
    return out


def extract_observations(groups: list | None) -> list[PairObs]:
    """All answered pairings, including in-progress. Soft answers excluded.

    Groups with empty pairings fall back to adjacent rank_order winner pairs.
    """
    out: list[PairObs] = []
    for gi, raw in enumerate(groups or []):
        g = _as_dict(raw)
        pid = int(g.get("participant_id") or 0)
        gt = _group_type(g)
        channel = "factor" if gt == "criteria" else "option"
        cid = g.get("criterion_id")
        factor_id = None if cid is None else _int_or_none(cid)
        gkey = _group_key(g, gi)
        pairings = g.get("pairings") or []
        used_legacy = False
        parsed: list[PairObs] = []
        if isinstance(pairings, list) and pairings:
            for seq, p in enumerate(pairings):
                obs = _usable_pairing(p)
                if obs is None:
                    continue
                parsed.append(obs)
        if not parsed:
            for seq, (w, l) in enumerate(_adjacent_from_rank_order(g.get("rank_order") or [])):
                parsed.append(PairObs(
                    participant_id=0,
                    channel="",
                    factor_id=None,
                    winner_id=w,
                    loser_id=l,
                    y=1.0,
                    left_sign=0.0,
                    group_key="",
                    seq=seq,
                    response="winner",
                    legacy=True,
                ))
                used_legacy = True
        for seq, obs in enumerate(parsed):
            out.append(PairObs(
                participant_id=pid,
                channel=channel,
                factor_id=factor_id,
                winner_id=obs.winner_id,
                loser_id=obs.loser_id,
                y=obs.y,
                left_sign=obs.left_sign,
                group_key=gkey,
                seq=seq,
                response=obs.response,
                legacy=used_legacy or obs.legacy,
            ))
    return out


def fingerprint_observations(obs: list[PairObs]) -> str:
    import hashlib

    parts = [
        f"{o.participant_id}:{o.channel}:{o.factor_id}:{o.group_key}:{o.seq}:"
        f"{o.winner_id}:{o.loser_id}:{o.y}:{o.response}"
        for o in obs
    ]
    parts.sort()
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def channel_groups(obs: list[PairObs]) -> dict[tuple[str, int | None], list[PairObs]]:
    by: dict[tuple[str, int | None], list[PairObs]] = {}
    for o in obs:
        by.setdefault((o.channel, o.factor_id), []).append(o)
    return by
