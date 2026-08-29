from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from .sort_compare import ford_johnson_budget, max_unique_pairs

PairResponse = Literal["winner", "tie", "unsure", "skipped"]
RankingTargetMode = Literal["winner", "top_n", "full"]


@dataclass
class PairAnswer:
    item_a: int
    item_b: int
    winner_id: int | None
    response: str
    presented_left_id: int
    presented_right_id: int
    decision_seconds: float = 0.0


@dataclass
class RankingTarget:
    mode: RankingTargetMode
    n: int | None = None


@dataclass
class SchedulerState:
    items: list[int]
    target: RankingTarget
    pass_index: int
    question_budget: int
    answers: list[PairAnswer] = field(default_factory=list)
    prior_answers: list[PairAnswer] = field(default_factory=list)
    last_pair: tuple[int, int] | None = None


def pair_key(a: int, b: int) -> str:
    return f"{a},{b}" if a < b else f"{b},{a}"


def hash_seed(parts: list[str | int]) -> int:
    s = "|".join(str(p) for p in parts)
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def seeded_unit(seed: int) -> float:
    x = math.sin(seed) * 10000
    return x - math.floor(x)


def fit_provisional_scores(items: list[int], answers: list[PairAnswer]) -> dict[int, float]:
    scores = {int(i): 0.0 for i in items}
    usable = [a for a in answers if a.response in ("winner", "tie")]
    if not usable:
        return scores
    lr = 0.25
    reg = 0.08
    for _iter in range(24):
        grad = {int(i): reg * scores.get(int(i), 0.0) for i in items}
        for ans in usable:
            sa = scores.get(ans.item_a, 0.0)
            sb = scores.get(ans.item_b, 0.0)
            p = 1.0 / (1.0 + math.exp(-(sa - sb)))
            if ans.response == "tie":
                y = 0.5
            else:
                y = 1.0 if ans.winner_id == ans.item_a else 0.0
            g = p - y
            grad[ans.item_a] = grad.get(ans.item_a, 0.0) + g
            grad[ans.item_b] = grad.get(ans.item_b, 0.0) - g
        for item_id in items:
            scores[item_id] = scores.get(item_id, 0.0) - lr * grad.get(item_id, 0.0)
        mean = sum(scores.get(item_id, 0.0) for item_id in items) / len(items)
        for item_id in items:
            scores[item_id] = scores.get(item_id, 0.0) - mean
    return scores


def ranks_from_scores(items: list[int], scores: dict[int, float]) -> dict[int, int]:
    ordered = sorted(items, key=lambda i: (-(scores.get(i, 0.0)), i))
    return {item_id: idx + 1 for idx, item_id in enumerate(ordered)}


def components(items: list[int], edges: list[tuple[int, int]]) -> list[list[int]]:
    adj: dict[int, list[int]] = {int(i): [] for i in items}
    for a, b in edges:
        if a in adj:
            adj[a].append(b)
        if b in adj:
            adj[b].append(a)
    seen: set[int] = set()
    out: list[list[int]] = []
    for item_id in items:
        if item_id in seen:
            continue
        stack = [item_id]
        comp: list[int] = []
        seen.add(item_id)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in adj.get(cur, []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        out.append(comp)
    return out


def used_pair_set(answers: list[PairAnswer]) -> set[str]:
    return {pair_key(a.item_a, a.item_b) for a in answers}


def historical_stats(prior: list[PairAnswer], a: int, b: int) -> dict[str, int]:
    count = 0
    wins_a = 0
    wins_b = 0
    key = pair_key(a, b)
    for p in prior:
        if pair_key(p.item_a, p.item_b) != key:
            continue
        count += 1
        if p.response != "winner" or p.winner_id is None:
            continue
        if p.winner_id == a:
            wins_a += 1
        elif p.winner_id == b:
            wins_b += 1
    return {"count": count, "winsA": wins_a, "winsB": wins_b}


def enumerate_legal_pairs(state: SchedulerState) -> list[tuple[int, int]]:
    used = used_pair_set(state.answers)
    last = state.last_pair
    all_pairs: list[tuple[int, int]] = []
    disjoint: list[tuple[int, int]] = []
    n = len(state.items)
    for i in range(n):
        for j in range(i + 1, n):
            a = state.items[i]
            b = state.items[j]
            if pair_key(a, b) in used:
                continue
            all_pairs.append((a, b))
            if not last or (a != last[0] and a != last[1] and b != last[0] and b != last[1]):
                disjoint.append((a, b))
    return disjoint if disjoint else all_pairs


def unseen_items(state: SchedulerState) -> list[int]:
    seen: set[int] = set()
    for a in state.answers:
        seen.add(a.item_a)
        seen.add(a.item_b)
    return [item_id for item_id in state.items if item_id not in seen]


def remains_feasible(state: SchedulerState, pair: tuple[int, int]) -> bool:
    remaining_after = state.question_budget - len(state.answers) - 1
    if remaining_after <= 0:
        return True
    next_state = SchedulerState(
        items=state.items,
        target=state.target,
        pass_index=state.pass_index,
        question_budget=state.question_budget,
        answers=list(state.answers) + [
            PairAnswer(
                item_a=pair[0],
                item_b=pair[1],
                winner_id=pair[0],
                response="winner",
                presented_left_id=pair[0],
                presented_right_id=pair[1],
                decision_seconds=0,
            )
        ],
        prior_answers=state.prior_answers,
        last_pair=pair,
    )
    legal = enumerate_legal_pairs(next_state)
    if not legal:
        return False
    if state.pass_index == 1:
        unseen = unseen_items(next_state)
        if len(unseen) > remaining_after * 2:
            return False
        if len(unseen) == 1:
            u = unseen[0]
            can_cover = any(a == u or b == u for a, b in legal)
            if not can_cover and remaining_after == 1:
                return False
    return True


def acquisition_score(
    state: SchedulerState,
    pair: tuple[int, int],
    scores: dict[int, float],
    ranks: dict[int, int],
) -> float:
    a, b = pair
    sa = scores.get(a, 0.0)
    sb = scores.get(b, 0.0)
    p = 1.0 / (1.0 + math.exp(-(sa - sb)))
    info = 4.0 * p * (1.0 - p)
    ra = ranks.get(a, 1)
    rb = ranks.get(b, 1)
    n = len(state.items)
    top_n = max(1, min(state.target.n or 1, math.floor(n / 2) or 1))
    t = 1.0
    if state.target.mode == "winner":
        ta = math.exp(-(ra - 1) / 2)
        tb = math.exp(-(rb - 1) / 2)
        t = (ta + tb) / 2
        if ra == 1 or rb == 1:
            t += 0.35
    elif state.target.mode == "top_n":
        ordered = sorted(state.items, key=lambda x: ranks.get(x, 0))
        if len(ordered) > top_n:
            boundary = (scores.get(ordered[top_n - 1], 0.0) + scores.get(ordered[top_n], 0.0)) / 2
        else:
            boundary = scores.get(ordered[-1], 0.0) if ordered else 0.0
        da = math.exp(-abs(sa - boundary) / 0.75)
        db = math.exp(-abs(sb - boundary) / 0.75)
        t = (da + db) / 2
        straddles = (ra <= top_n) != (rb <= top_n)
        if straddles:
            t += 0.55
    else:
        t = math.exp(-(abs(ra - rb) - 1) / 2.5)
    hist = historical_stats(state.prior_answers, a, b)
    r = 1.0 / math.sqrt(1 + 0.65 * hist["count"])
    exposure = {int(i): 0 for i in state.items}
    for ans in state.answers:
        exposure[ans.item_a] = exposure.get(ans.item_a, 0) + 1
        exposure[ans.item_b] = exposure.get(ans.item_b, 0) + 1
    e = 1 + 0.15 * (2 - min(exposure.get(a, 0), 2) - min(exposure.get(b, 0), 2))
    edges: list[tuple[int, int]] = []
    for ans in [*state.prior_answers, *state.answers]:
        if ans.response in ("unsure", "skipped"):
            continue
        edges.append((ans.item_a, ans.item_b))
    comps = components(state.items, edges)
    in_same = any(a in c and b in c for c in comps)
    g = 1.0 if in_same else 2.4
    bonus = 0.0
    if hist["count"] >= 2 and hist["winsA"] and hist["winsB"]:
        bonus += 0.25
    return info * t * r * e * g + bonus


def select_next_pair(state: SchedulerState) -> tuple[int, int] | None:
    if len(state.answers) >= state.question_budget:
        return None
    if len(state.items) < 2:
        return None
    pair_cap = max_unique_pairs(len(state.items))
    if len(state.answers) >= pair_cap:
        return None
    candidates = enumerate_legal_pairs(state)
    if not candidates:
        return None
    require_coverage = state.pass_index == 1
    unseen = unseen_items(state)
    if require_coverage and len(unseen) >= 2:
        unseen_set = set(unseen)
        both_unseen = [(a, b) for a, b in candidates if a in unseen_set and b in unseen_set]
        if both_unseen:
            candidates = both_unseen
    elif require_coverage and len(unseen) == 1:
        u = unseen[0]
        cover = [(a, b) for a, b in candidates if a == u or b == u]
        if cover:
            candidates = cover
    feasible = [pair for pair in candidates if remains_feasible(state, pair)]
    pool = feasible if feasible else candidates
    all_answers = [*state.prior_answers, *state.answers]
    scores = fit_provisional_scores(state.items, all_answers)
    ranks = ranks_from_scores(state.items, scores)
    best = pool[0]
    best_score = float("-inf")
    seed = hash_seed([state.pass_index, state.question_budget, *state.items])
    for i, pair in enumerate(pool):
        s = acquisition_score(state, pair, scores, ranks)
        s += seeded_unit(seed + i) * 1e-6
        if s > best_score:
            best_score = s
            best = pair
    return best


def choose_orientation(
    a: int,
    b: int,
    history: list[PairAnswer],
    seed_parts: list[str | int],
) -> tuple[int, int]:
    left_a = 0
    left_b = 0
    for h in history:
        if h.presented_left_id == a:
            left_a += 1
        if h.presented_left_id == b:
            left_b += 1
    if left_a < left_b:
        return a, b
    if left_b < left_a:
        return b, a
    if seeded_unit(hash_seed([*seed_parts, a, b])) < 0.5:
        return a, b
    return b, a


def rank_order_from_answers(items: list[int], answers: list[PairAnswer]) -> list[int]:
    scores = fit_provisional_scores(items, answers)
    return sorted(items, key=lambda i: (-(scores.get(i, 0.0)), i))


def suggested_budget(n: int) -> int:
    return ford_johnson_budget(n)


def pairing_to_answer(p: dict) -> PairAnswer | None:
    try:
        left_raw = p.get("presented_left_id", p.get("presentedLeftId", p.get("item_a_id", p.get("winner_id"))))
        right_raw = p.get("presented_right_id", p.get("presentedRightId", p.get("item_b_id", p.get("loser_id"))))
        a_raw = p.get("item_a_id", p.get("winner_id", left_raw))
        b_raw = p.get("item_b_id", p.get("loser_id", right_raw))
        a = int(a_raw)
        b = int(b_raw)
    except (TypeError, ValueError):
        return None
    if a == b:
        return None
    try:
        left = int(left_raw) if left_raw is not None else a
        right = int(right_raw) if right_raw is not None else b
    except (TypeError, ValueError):
        left, right = a, b
    response = str(p.get("response") or "winner")
    winner_raw = p.get("winner_id")
    try:
        winner = int(winner_raw) if winner_raw is not None else (a if response == "winner" else None)
    except (TypeError, ValueError):
        winner = a if response == "winner" else None
    try:
        seconds = float(p.get("decision_seconds", p.get("decisionSeconds", 0)) or 0)
    except (TypeError, ValueError):
        seconds = 0.0
    return PairAnswer(
        item_a=a,
        item_b=b,
        winner_id=winner,
        response=response,
        presented_left_id=left,
        presented_right_id=right,
        decision_seconds=seconds,
    )


def pairings_to_answers(rows: list | None) -> list[PairAnswer]:
    out: list[PairAnswer] = []
    for p in rows or []:
        if not isinstance(p, dict):
            continue
        ans = pairing_to_answer(p)
        if ans is not None:
            out.append(ans)
    return out


def answer_to_pairing(ans: PairAnswer) -> dict:
    loser = ans.item_b if ans.winner_id == ans.item_a else ans.item_a
    if ans.response != "winner" or ans.winner_id is None:
        winner = ans.presented_left_id
        loser = ans.presented_right_id
    else:
        winner = ans.winner_id
        loser = ans.item_b if winner == ans.item_a else ans.item_a
        if loser == winner:
            loser = ans.presented_right_id if winner == ans.presented_left_id else ans.presented_left_id
    return {
        "winner_id": int(winner),
        "loser_id": int(loser),
        "response": str(ans.response),
        "decision_seconds": float(ans.decision_seconds or 0.0),
        "presented_left_id": int(ans.presented_left_id),
        "presented_right_id": int(ans.presented_right_id),
        "item_a_id": int(ans.item_a),
        "item_b_id": int(ans.item_b),
        "effective_rule": "choice",
    }


def ranking_target_from_group(group: dict) -> RankingTarget:
    mode = str(group.get("ranking_target") or "full").strip().lower()
    if mode in ("winner", "find_best"):
        return RankingTarget(mode="winner", n=1)
    if mode in ("top_n", "find_top_3", "find_top_half"):
        n = group.get("top_n")
        try:
            top_n = int(n) if n is not None else 1
        except (TypeError, ValueError):
            top_n = 1
        return RankingTarget(mode="top_n", n=max(1, top_n))
    return RankingTarget(mode="full")
