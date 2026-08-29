"""Comparison-count estimates, sort algorithm selection, and rank reconstruction."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Callable, Literal

SortAlgorithm = Literal["ford_johnson", "merge_sort"]

FJ_MAX_N = 40


def select_sort_algorithm(n: int) -> SortAlgorithm:
    if n <= FJ_MAX_N:
        return "ford_johnson"
    return "merge_sort"


def _jacobsthal(k: int) -> int:
    if k <= 0:
        return 0
    if k == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, k + 1):
        a, b = b, b + 2 * a
    return b


def ford_johnson_rank(ids: list[int], cmp: Callable[[int, int], int]) -> list[int]:
    """
    Ford–Johnson producing best→worst order.
    cmp(a, b) returns the better id (winner).
    Losers insert strictly after their paired winner (minIndex = wi + 1).
    """
    items = [int(x) for x in ids]
    if len(items) <= 1:
        return items[:]
    if len(items) == 2:
        w = cmp(items[0], items[1])
        return [w, items[0] if w == items[1] else items[1]]

    pairs: list[tuple[int, int]] = []
    leftover = items[-1] if len(items) % 2 == 1 else None
    n_pairs = len(items) // 2
    for i in range(n_pairs):
        a, b = items[i * 2], items[i * 2 + 1]
        w = cmp(a, b)
        pairs.append((w, b if w == a else a))

    winners = [w for w, _ in pairs]
    main = ford_johnson_rank(winners, cmp)
    loser_of = {w: l for w, l in pairs}

    losers_ordered: list[int] = []
    inserted: set[int] = set()
    if main:
        fl = loser_of.get(main[0])
        if fl is not None:
            losers_ordered.append(fl)
            inserted.add(fl)
    k = 1
    while len(inserted) < len(pairs):
        jk = _jacobsthal(k + 1)
        jk_prev = _jacobsthal(k)
        hi = min(jk, len(main)) - 1
        lo = jk_prev
        for i in range(hi, lo - 1, -1):
            if 0 <= i < len(main):
                l = loser_of.get(main[i])
                if l is not None and l not in inserted:
                    losers_ordered.append(l)
                    inserted.add(l)
        k += 1
        if k > 64:
            break
    for _, l in pairs:
        if l not in inserted:
            losers_ordered.append(l)
            inserted.add(l)

    def binary_insert(item: int, min_index: int) -> None:
        lo = max(0, min(min_index, len(main)))
        hi = len(main)
        while lo < hi:
            mid = (lo + hi) // 2
            better = cmp(item, main[mid])
            if better == item:
                hi = mid
            else:
                lo = mid + 1
        main.insert(lo, item)

    for loser in losers_ordered:
        paired_winner = next((w for w, l in pairs if l == loser), None)
        wi = main.index(paired_winner) if paired_winner in main else -1
        min_idx = 0 if wi < 0 else wi + 1
        binary_insert(loser, min_idx)
    if leftover is not None:
        binary_insert(leftover, 0)
    return main


def _pairing_winner_loser(p: dict[str, Any]) -> tuple[int, int, str] | None:
    resp = str(p.get("response") or "winner").lower()
    try:
        w = int(p.get("winner_id"))
        l = int(p.get("loser_id"))
    except (TypeError, ValueError):
        return None
    if w == l:
        return None
    return w, l, resp


def _is_permutation(order: list[int], ids: list[int]) -> bool:
    if not order or len(order) != len(ids):
        return False
    return sorted(order) == sorted(ids) and len(set(order)) == len(order)


def _order_consistent_with_pairings(order: list[int], pairings: list[dict] | None) -> bool:
    """True when every hard pairing has winner ranked before loser in order."""
    if not order:
        return False
    pos = {int(x): i for i, x in enumerate(order)}
    for raw in pairings or []:
        parsed = _pairing_winner_loser(raw if isinstance(raw, dict) else {})
        if not parsed:
            continue
        w, l, resp = parsed
        if resp in ("unsure", "skipped", "tie"):
            continue
        if w not in pos or l not in pos:
            continue
        if pos[w] > pos[l]:
            return False
    return True


def rank_order_from_pairings(
    item_ids: list[int] | None,
    pairings: list[dict] | None,
    *,
    stored_rank_order: list[int] | None = None,
) -> list[int]:
    """
    Reconstruct best→worst order from recorded pair outcomes.

    Does **not** re-run Ford–Johnson: stored pairings are a path-dependent subset
    of comparisons, and inventing outcomes for unasked pairs (e.g. id_asc) corrupts
    the order.

    Prefer a stored total order when it is a full permutation of the items and
    consistent with every hard pairing (winner before loser). That keeps correct
    client FJ output (including reverse axes). Otherwise use Copeland on known
    pairs only — repairing historical rows from the FJ insert bug (losers placed
    before winners):

      score = wins − losses
      tie-break = wins, then −losses, then strength-of-schedule (sum of beaten scores)
    """
    ids = [int(x) for x in (item_ids or stored_rank_order or []) if x is not None]
    if not ids and stored_rank_order:
        ids = [int(x) for x in stored_rank_order]
    if not ids:
        return []
    if len(ids) == 1:
        return ids[:]

    stored = [int(x) for x in (stored_rank_order or [])]
    if stored and _is_permutation(stored, ids) and _order_consistent_with_pairings(stored, pairings):
        return stored

    id_set = set(ids)
    wins: dict[int, float] = {i: 0.0 for i in ids}
    losses: dict[int, float] = {i: 0.0 for i in ids}
    beaten: dict[int, list[int]] = defaultdict(list)
    known_pairs = 0
    for raw in pairings or []:
        parsed = _pairing_winner_loser(raw if isinstance(raw, dict) else {})
        if not parsed:
            continue
        w, l, resp = parsed
        if w not in id_set or l not in id_set:
            continue
        if resp in ("unsure", "skipped"):
            continue
        if resp == "tie":
            wins[w] += 0.5
            wins[l] += 0.5
            known_pairs += 1
            continue
        wins[w] += 1.0
        losses[l] += 1.0
        beaten[w].append(l)
        known_pairs += 1

    if known_pairs == 0:
        return [int(x) for x in (stored_rank_order or ids)]

    copeland = {i: wins[i] - losses[i] for i in ids}
    # One-pass strength: sum of copeland of defeated opponents
    sos = {
        i: sum(copeland.get(j, 0.0) for j in beaten.get(i, []))
        for i in ids
    }
    return sorted(
        ids,
        key=lambda i: (-copeland[i], -wins[i], losses[i], -sos[i], i),
    )


def effective_group_rank_order(group: dict[str, Any]) -> list[int]:
    """Best→worst ids for a stored group row (keeps consistent order; repairs bugs)."""
    pairings = group.get("pairings") or []
    stored = [int(x) for x in (group.get("rank_order") or [])]
    initial = [int(x) for x in (group.get("item_ids_initial") or group.get("item_ids") or stored)]
    ids = initial or stored
    if stored and _is_permutation(stored, ids if ids else stored) and _order_consistent_with_pairings(
        stored, pairings
    ):
        return stored
    if pairings:
        return rank_order_from_pairings(ids, pairings, stored_rank_order=stored)
    return stored


def ford_johnson_budget(n: int) -> int:
    """Ford–Johnson / Merge-Insertion worst-case comparison count: Σ ceil(log2(3i/4))."""
    if n <= 1:
        return 0
    total = 0
    for i in range(1, n + 1):
        total += math.ceil(math.log2((3 * i) / 4))
    return int(total)


def default_questions_per_group() -> int:
    try:
        from ..config.config_settings import settings
        v = int(getattr(settings, "COMPARE_DEFAULT_QUESTIONS_PER_GROUP", 20) or 20)
    except (TypeError, ValueError, AttributeError):
        v = 20
    return max(1, min(500, v))


def max_unique_pairs(n: int) -> int:
    if n < 2:
        return 0
    return n * (n - 1) // 2


def max_items_for_question_budget(budget: int) -> int:
    """Largest item count whose Ford–Johnson budget is <= question budget."""
    if budget <= 0:
        return 2
    k = 2
    while ford_johnson_budget(k + 1) <= budget and k < 500:
        k += 1
    return k


def question_budget_bounds(n: int) -> tuple[int, int]:
    """Allowed questions-per-group range: [ceil(FJ(n)/2), FJ(n)*2], capped at unique pairs."""
    fj = ford_johnson_budget(n)
    if fj <= 0:
        return (0, 0)
    pair_cap = max_unique_pairs(n)
    lo = max(1, min(pair_cap, (fj + 1) // 2))
    hi = max(lo, min(pair_cap, fj * 2))
    return lo, hi


def clamp_questions_per_group_stored(value: int | None) -> int:
    """Wide persistence clamp when the item count is not known yet."""
    default = default_questions_per_group()
    try:
        v = int(value if value is not None else default)
    except (TypeError, ValueError):
        v = default
    return max(1, min(500, v))


def clamp_questions_per_group(value: int | None, n: int) -> int:
    stored = clamp_questions_per_group_stored(value)
    lo, hi = question_budget_bounds(n)
    if hi <= 0:
        return stored
    return max(lo, min(hi, stored))


def default_questions_per_group_for_n(n: int) -> int:
    """Two-thirds of the Ford–Johnson budget for n items, then clamp; stored default when n < 2."""
    if n < 2:
        return default_questions_per_group()
    scaled = int(math.floor(ford_johnson_budget(n) * 2 / 3 + 0.5))
    return clamp_questions_per_group(scaled, n)


def resolve_questions_per_group(
    value: int | None,
    n: int,
    explicit: bool = False,
) -> int:
    """Effective questions-per-group: FJ default unless the user overrode it."""
    if not explicit:
        return default_questions_per_group_for_n(n)
    return clamp_questions_per_group(value, n)


def ford_johnson_upper_bound(n: int) -> int:
    """Standard information-theoretic upper bound used by FJ analysis: n⌈lg n⌉ − 2^⌈lg n⌉ + 1."""
    if n <= 1:
        return 0
    if n == 2:
        return 1
    lg = math.ceil(math.log2(n))
    return int(n * lg - (1 << lg) + 1)


def merge_sort_upper_bound(n: int) -> int:
    """Classic merge-sort comparison upper bound: n⌈lg n⌉ − n + 1."""
    if n <= 1:
        return 0
    if n == 2:
        return 1
    lg = math.ceil(math.log2(n))
    return int(n * lg - n + 1)


def estimated_comparisons(n: int, algorithm: SortAlgorithm | None = None) -> int:
    algo = algorithm or select_sort_algorithm(n)
    if algo == "ford_johnson":
        return ford_johnson_upper_bound(n)
    return merge_sort_upper_bound(n)


def clamp_min_expected_passes(value: int | None) -> int:
    try:
        v = int(value if value is not None else 2)
    except (TypeError, ValueError):
        v = 2
    return max(1, min(5, v))


def clamp_max_recommended_passes(value: int | None, min_passes: int | None = None) -> int:
    lo = clamp_min_expected_passes(min_passes)
    try:
        v = int(value if value is not None else lo)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(10, v))


def hard_max_passes(max_recommended: int | None, min_passes: int | None = None) -> int:
    return clamp_max_recommended_passes(max_recommended, min_passes) + 1
