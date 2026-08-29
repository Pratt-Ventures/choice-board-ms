"""Unit tests for sort comparison bounds and mean-rank Results."""
from src.utils.sort_compare import (
    estimated_comparisons,
    ford_johnson_budget,
    ford_johnson_upper_bound,
    question_budget_bounds,
    clamp_questions_per_group,
    clamp_questions_per_group_stored,
    default_questions_per_group,
    default_questions_per_group_for_n,
    resolve_questions_per_group,
    merge_sort_upper_bound,
    select_sort_algorithm,
    clamp_min_expected_passes,
    clamp_max_recommended_passes,
    hard_max_passes,
    ford_johnson_rank,
    rank_order_from_pairings,
    effective_group_rank_order,
)
from src.utils.vote_sort_session import (
    pick_next_sort_group,
    excluded_option_ids,
    option_batch_count,
    ranking_evidence_from_groups,
    required_slots_for_pass,
    resolved_question_budgets,
    serialize_criterion,
    serialize_item,
    validate_group_package,
)
from src.utils.vote_ranking import (
    build_report,
    participant_rank_bundle,
    project_metrics,
    within_participant_stability,
)


def test_algorithm_threshold():
    assert select_sort_algorithm(40) == "ford_johnson"
    assert select_sort_algorithm(41) == "merge_sort"


def test_ford_johnson_respects_total_order():
    """cmp encodes a total order 1 > 2 > 3 > 4 > 5; FJ must recover it."""
    pref = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}

    def cmp(a, b):
        return a if pref[a] < pref[b] else b

    for seed_order in (
        [1, 2, 3, 4, 5],
        [5, 4, 3, 2, 1],
        [3, 1, 5, 2, 4],
        [5, 1, 2, 4, 3],
    ):
        out = ford_johnson_rank(seed_order, cmp)
        assert out == [1, 2, 3, 4, 5], seed_order


def test_rank_order_from_pairings_repairs_buggy_stored_order():
    """Project-1150-style: pairings crown option 1; stored order wrongly led with 5."""
    ids = [1651, 1647, 1648, 1650, 1649]
    pairings = [
        {"winner_id": 1647, "loser_id": 1651, "response": "winner"},
        {"winner_id": 1648, "loser_id": 1650, "response": "winner"},
        {"winner_id": 1647, "loser_id": 1648, "response": "winner"},
        {"winner_id": 1647, "loser_id": 1650, "response": "winner"},
        {"winner_id": 1649, "loser_id": 1650, "response": "winner"},
        {"winner_id": 1647, "loser_id": 1649, "response": "winner"},
    ]
    stored_bug = [1651, 1647, 1649, 1650, 1648]
    fixed = rank_order_from_pairings(ids, pairings, stored_rank_order=stored_bug)
    assert fixed[0] == 1647  # Option 1 best
    assert fixed.index(1648) < fixed.index(1650)
    assert fixed.index(1649) < fixed.index(1650)
    g = {
        "item_ids_initial": ids,
        "rank_order": stored_bug,
        "pairings": pairings,
    }
    assert effective_group_rank_order(g)[0] == 1647


def test_rank_order_from_pairings_f2_reverse_style():
    """Opt5 beats Opt4 beats others → Opt5 first (not invented id_asc ties)."""
    ids = [1649, 1647, 1650, 1648, 1651]
    pairings = [
        {"winner_id": 1649, "loser_id": 1647, "response": "winner"},
        {"winner_id": 1650, "loser_id": 1648, "response": "winner"},
        {"winner_id": 1650, "loser_id": 1649, "response": "winner"},
        {"winner_id": 1650, "loser_id": 1647, "response": "winner"},
        {"winner_id": 1651, "loser_id": 1647, "response": "winner"},
        {"winner_id": 1651, "loser_id": 1650, "response": "winner"},
        {"winner_id": 1651, "loser_id": 1648, "response": "winner"},
    ]
    fixed = rank_order_from_pairings(ids, pairings)
    assert fixed[0] == 1651
    assert fixed.index(1650) < fixed.index(1647)
    assert fixed[-1] == 1647


def test_project_1224_p2_f2_keeps_full_reverse_when_stored_consistent():
    """
    Project 1224 pass-2 F2: client stored 5>4>3>2>1 (option numbers) with pairings
    that include 2>1. Naive Copeland on the incomplete FJ graph yields 5,4,3,1,2;
    effective order must keep the consistent stored total order.
    """
    # option numbers 1..5 as stand-ins for ids 1711..1715
    ids = [1, 2, 3, 5, 4]
    stored = [5, 4, 3, 2, 1]
    pairings = [
        {"winner_id": 2, "loser_id": 1, "response": "winner"},
        {"winner_id": 5, "loser_id": 3, "response": "winner"},
        {"winner_id": 5, "loser_id": 2, "response": "winner"},
        {"winner_id": 3, "loser_id": 2, "response": "winner"},
        {"winner_id": 4, "loser_id": 2, "response": "winner"},
        {"winner_id": 4, "loser_id": 3, "response": "winner"},
        {"winner_id": 5, "loser_id": 4, "response": "winner"},
    ]
    # Without trusting stored, Copeland demotes 2 below 1
    copeland_only = rank_order_from_pairings(ids, pairings, stored_rank_order=None)
    assert copeland_only == [5, 4, 3, 1, 2]
    kept = rank_order_from_pairings(ids, pairings, stored_rank_order=stored)
    assert kept == [5, 4, 3, 2, 1]
    g = {"item_ids_initial": ids, "rank_order": stored, "pairings": pairings}
    assert effective_group_rank_order(g) == [5, 4, 3, 2, 1]


def test_fj_reverse_axis_effective_order_matches_client_for_all_seeds():
    """Deliberate reverse total order 5>4>3>2>1: FJ rank_order must survive Results."""
    pref = {5: 0, 4: 1, 3: 2, 2: 3, 1: 4}

    def true_cmp(a, b):
        return a if pref[a] < pref[b] else b

    for seed in (
        [1, 2, 3, 4, 5],
        [5, 4, 3, 2, 1],
        [3, 5, 4, 2, 1],
        [1, 2, 3, 5, 4],
        [2, 4, 1, 5, 3],
    ):
        pairings: list[dict] = []

        def cmp_log(a, b):
            w = true_cmp(a, b)
            pairings.append(
                {"winner_id": w, "loser_id": (b if w == a else a), "response": "winner"}
            )
            return w

        order = ford_johnson_rank(seed, cmp_log)
        assert order == [5, 4, 3, 2, 1], seed
        g = {"item_ids_initial": seed, "rank_order": order, "pairings": pairings}
        assert effective_group_rank_order(g) == [5, 4, 3, 2, 1], seed


def test_mean_rank_by_factor_full_reverse_multi_pass():
    """Two reverse F2 passes must not flip mid options via Copeland + id tie-break."""
    alts = [{"id": i, "alternative_title": f"O{i}"} for i in range(1, 6)]
    facs = [{"id": 10, "factor_title": "F1"}, {"id": 11, "factor_title": "F2"}]
    # p1 F2 reverse pairings (project 1224 pass1 style) + p2 F2 (pass2 style)
    p1_f2_pairs = [
        {"winner_id": 5, "loser_id": 3, "response": "winner"},
        {"winner_id": 4, "loser_id": 2, "response": "winner"},
        {"winner_id": 5, "loser_id": 4, "response": "winner"},
        {"winner_id": 4, "loser_id": 3, "response": "winner"},
        {"winner_id": 3, "loser_id": 2, "response": "winner"},
        {"winner_id": 3, "loser_id": 1, "response": "winner"},
        {"winner_id": 2, "loser_id": 1, "response": "winner"},
    ]
    p2_f2_pairs = [
        {"winner_id": 2, "loser_id": 1, "response": "winner"},
        {"winner_id": 5, "loser_id": 3, "response": "winner"},
        {"winner_id": 5, "loser_id": 2, "response": "winner"},
        {"winner_id": 3, "loser_id": 2, "response": "winner"},
        {"winner_id": 4, "loser_id": 2, "response": "winner"},
        {"winner_id": 4, "loser_id": 3, "response": "winner"},
        {"winner_id": 5, "loser_id": 4, "response": "winner"},
    ]
    rev = [5, 4, 3, 2, 1]
    fwd = [1, 2, 3, 4, 5]
    groups = [
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 1,
            "rank_order": fwd,
            "item_ids_initial": fwd,
            "pairings": [
                {"winner_id": a, "loser_id": b, "response": "winner"}
                for a, b in zip(fwd, fwd[1:])
            ],
            "comparison_count": 4,
        },
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 11,
            "pass_index": 1,
            "rank_order": rev,
            "item_ids_initial": [3, 5, 4, 2, 1],
            "pairings": p1_f2_pairs,
            "comparison_count": 7,
        },
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 2,
            "rank_order": fwd,
            "item_ids_initial": fwd,
            "pairings": [
                {"winner_id": a, "loser_id": b, "response": "winner"}
                for a, b in zip(fwd, fwd[1:])
            ],
            "comparison_count": 4,
        },
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 11,
            "pass_index": 2,
            "rank_order": rev,
            "item_ids_initial": [1, 2, 3, 5, 4],
            "pairings": p2_f2_pairs,
            "comparison_count": 7,
        },
        {
            "participant_id": 1,
            "group_type": "criteria",
            "criterion_id": None,
            "pass_index": 1,
            "rank_order": [10, 11],
            "pairings": [{"winner_id": 10, "loser_id": 11, "response": "winner"}],
            "comparison_count": 1,
        },
        {
            "participant_id": 1,
            "group_type": "criteria",
            "criterion_id": None,
            "pass_index": 2,
            "rank_order": [10, 11],
            "pairings": [{"winner_id": 10, "loser_id": 11, "response": "winner"}],
            "comparison_count": 1,
        },
    ]
    report = build_report(
        alternatives=alts,
        factors=facs,
        all_groups=groups,
        participants=[{"id": 1}],
        settings={"participant_influence_mode": "comparisons"},
    )
    f2_ids = [row["id"] for row in report["by_factor"][11]]
    assert f2_ids == [5, 4, 3, 2, 1], f2_ids


def test_bounds_monotonic():
    prev = 0
    for n in range(1, 50):
        c = estimated_comparisons(n)
        assert c >= prev or n <= 2
        prev = c
    assert ford_johnson_upper_bound(2) == 1
    assert merge_sort_upper_bound(4) >= 3


def test_ford_johnson_budget_known_values():
    assert ford_johnson_budget(0) == 0
    assert ford_johnson_budget(1) == 0
    assert ford_johnson_budget(2) == 1
    assert ford_johnson_budget(3) == 3
    assert ford_johnson_budget(4) == 5
    assert ford_johnson_budget(5) == 7
    assert ford_johnson_budget(6) == 10
    assert ford_johnson_budget(7) == 13
    assert ford_johnson_budget(8) == 16


def test_question_budget_bounds_and_clamp():
    lo, hi = question_budget_bounds(5)
    assert lo == 4
    assert hi == 10
    assert clamp_questions_per_group(20, 5) == 10
    assert clamp_questions_per_group(2, 5) == 4
    assert clamp_questions_per_group(10, 5) == 10
    assert clamp_questions_per_group(None, 2) == 1
    assert clamp_questions_per_group_stored(None) == 20
    assert clamp_questions_per_group_stored(0) == 1
    assert clamp_questions_per_group_stored(999) == 500
    assert question_budget_bounds(1) == (0, 0)


def test_resolve_questions_per_group_follows_fj_until_explicit():
    assert default_questions_per_group_for_n(0) == default_questions_per_group()
    assert default_questions_per_group_for_n(1) == default_questions_per_group()
    assert default_questions_per_group_for_n(2) == 1
    assert default_questions_per_group_for_n(5) == 5
    assert default_questions_per_group_for_n(8) == 11
    assert resolve_questions_per_group(20, 12, explicit=False) == default_questions_per_group_for_n(12)
    assert resolve_questions_per_group(20, 12, explicit=True) == 20
    assert resolve_questions_per_group(2, 5, explicit=True) == 4


def test_pass_clamps():
    assert clamp_min_expected_passes(0) == 1
    assert clamp_min_expected_passes(9) == 5
    assert clamp_max_recommended_passes(2, 3) == 3
    assert clamp_max_recommended_passes(None, 2) == 2
    assert clamp_max_recommended_passes(1, 1) == 1
    assert clamp_max_recommended_passes(2, 5) == 5
    assert clamp_max_recommended_passes(11, 2) == 10
    assert hard_max_passes(4) == 5
    assert hard_max_passes(2, 2) == 3
    assert hard_max_passes(10) == 11


def test_required_slots_multi_factor():
    slots = required_slots_for_pass(pass_index=1, alternative_ids=[1, 2, 3], factor_ids=[10, 11])
    assert len(slots) == 3  # 2 option groups + 1 factor
    assert slots[-1]["group_type"] == "criteria"


def test_pick_next_group_basic():
    class P:
        project_exclusive_mode = False
        min_expected_passes = 2
        max_recommended_passes = 4

    alts = [{"id": 1, "alternative_title": "A"}, {"id": 2, "alternative_title": "B"}, {"id": 3, "alternative_title": "C"}]
    facs = [{"id": 10, "factor_title": "F1"}, {"id": 11, "factor_title": "F2"}]
    out = pick_next_sort_group(project=P(), alternatives=alts, factors=facs, groups=[])
    assert out["group"] is not None
    g = out["group"]
    assert g["sort_algorithm"] == "ford_johnson"
    assert len(g["items"]) >= 2
    assert g.get("group_token")
    assert g.get("question_budget") >= 1
    assert out["progress"]["min_expected_passes"] == 2
    assert isinstance(out["progress"].get("ranking_evidence"), list)
    assert out["progress"].get("ranking_option_ids") == [1, 2, 3]
    assert set(out["progress"].get("ranking_factor_ids") or []) == {10, 11}


def test_ranking_evidence_from_groups_is_compact_and_participant_local():
    groups = [
        {
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 1,
            "item_ids_initial": [1, 2, 3],
            "requested_pairing_count": 4,
            "ranking_target": "full",
            "client_group_id": "abc123xyz0",
            "pairings": [
                {
                    "winner_id": 1,
                    "loser_id": 2,
                    "response": "winner",
                    "presented_left_id": 1,
                    "presented_right_id": 2,
                    "decision_seconds": 0.4,
                }
            ],
        }
    ]
    ev = ranking_evidence_from_groups(groups)
    assert len(ev) == 1
    row = ev[0]
    assert row["group_type"] == "alternative"
    assert row["criterion_id"] == 10
    assert row["item_ids"] == [1, 2, 3]
    assert row["question_budget"] == 4
    assert row["pairings"][0]["winner_id"] == 1
    assert "decision_seconds" not in row["pairings"][0]


def test_serialize_criterion_includes_comparison_question():
    d = {
        "id": 10,
        "factor_title": "Engineering Cost",
        "factor_description": "Prefer lower cost",
        "compare_prompt": 'Enter a clear single question, like, "Which requires less engineering resources"',
        "comparison_question": "  Which option has lower Engineering Cost?  ",
    }
    item = serialize_item(d)
    assert "comparison_question" not in item
    crit = serialize_criterion(d)
    # legacy comparison_question is ignored; canonical compare_prompt is sole source
    assert crit["comparison_question"] is None
    assert crit["compare_prompt"] == 'Enter a clear single question, like, "Which requires less engineering resources"'
    assert serialize_criterion({**d, "compare_prompt": "   "})["compare_prompt"] is None
    assert serialize_criterion({**d, "comparison_question": "   "})["comparison_question"] is None

    class P:
        project_exclusive_mode = False
        min_expected_passes = 1
        max_recommended_passes = 2

    alts = [{"id": 1, "alternative_title": "A"}, {"id": 2, "alternative_title": "B"}]
    facs = [d]
    out = pick_next_sort_group(project=P(), alternatives=alts, factors=facs, groups=[])
    g = out["group"]
    assert g is not None
    assert g["group_type"] != "criteria"
    assert g["criterion"]["comparison_question"] is None
    assert g["criterion"]["compare_prompt"] == 'Enter a clear single question, like, "Which requires less engineering resources"'
    assert "comparison_question" not in g["items"][0]

    overall = pick_next_sort_group(project=P(), alternatives=alts, factors=[], groups=[])
    assert overall["group"]["criterion"]["comparison_question"] is None


def test_vote_session_uses_fj_default_until_group_size_explicit():
    class DefaultP:
        project_exclusive_mode = False
        min_expected_passes = 2
        max_recommended_passes = 4
        option_questions_per_group = 20
        factor_questions_per_group = 20
        option_questions_per_group_explicit = False
        factor_questions_per_group_explicit = False

    class CustomP(DefaultP):
        option_questions_per_group_explicit = True

    option_ids = list(range(1, 13))
    opt_default, _ = resolved_question_budgets(DefaultP(), 12, 0)
    opt_custom, _ = resolved_question_budgets(CustomP(), 12, 0)
    assert opt_default == default_questions_per_group_for_n(12)
    assert opt_custom == 20
    assert option_batch_count(0, opt_custom) == 0
    assert option_batch_count(1, opt_custom) == 0
    assert option_batch_count(12, opt_custom) == 1

    alts = [{"id": i, "alternative_title": f"O{i}"} for i in option_ids]
    out = pick_next_sort_group(project=DefaultP(), alternatives=alts, factors=[], groups=[])
    assert out["group"] is not None
    batch_n = len(out["group"]["item_ids"])
    assert 2 <= batch_n <= 12
    assert out["group"]["question_budget"] == clamp_questions_per_group(opt_default, batch_n)


def test_exclusion_pick_one():
    groups = [
        {
            "pass_index": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "rank_order": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "participant_id": 1,
            "comparison_count": 5,
        }
    ]
    excl = excluded_option_ids(
        exclusive_mode=True,
        all_option_ids=list(range(1, 11)),
        groups=groups,
    )
    # bottom 15% of 10 = 1
    assert len(excl) >= 1
    assert max(excl) in range(1, 11)


def test_exclusion_respects_pass_bound():
    """Same-pass exclusions must not apply: F1's pass-1 result cannot shrink F2's pass-1 slot."""
    groups = [
        {
            "pass_index": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "rank_order": [1, 2, 3, 4, 5, 6],
            "participant_id": 1,
            "comparison_count": 5,
        }
    ]
    # issuing another pass-1 slot: nothing completed below pass 1 → nothing excluded
    assert excluded_option_ids(
        exclusive_mode=True,
        all_option_ids=list(range(1, 7)),
        groups=groups,
        before_pass=1,
    ) == set()
    # issuing pass-2: pass-1 results exclude the bottom option (6)
    excl_p2 = excluded_option_ids(
        exclusive_mode=True,
        all_option_ids=list(range(1, 7)),
        groups=groups,
        before_pass=2,
    )
    assert excl_p2 == {6}
    # legacy call without a bound keeps prior behavior (max completed pass)
    assert excluded_option_ids(
        exclusive_mode=True,
        all_option_ids=list(range(1, 7)),
        groups=groups,
    ) == excl_p2


def test_next_group_keeps_full_option_set_within_pass():
    """After F1's pass-1 group completes, F2's pass-1 group must still cover every option."""
    class P:
        project_exclusive_mode = True
        min_expected_passes = 2
        max_recommended_passes = 3
        option_questions_per_group = 20
        factor_questions_per_group = 20
        option_questions_per_group_explicit = True
        factor_questions_per_group_explicit = False

    alts = [{"id": i, "alternative_title": f"O{i}"} for i in range(1, 7)]
    facs = [{"id": 10, "factor_title": "F1"}, {"id": 11, "factor_title": "F2"}]
    done = [
        {
            "pass_index": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "rank_order": [1, 2, 3, 4, 5, 6],
            "participant_id": 1,
            "comparison_count": 9,
        }
    ]
    out = pick_next_sort_group(project=P(), alternatives=alts, factors=facs, groups=done)
    g = out["group"]
    assert g is not None
    assert g["group_type"] == "alternative"
    assert sorted(g["item_ids"]) == [1, 2, 3, 4, 5, 6], g["item_ids"]


def test_next_group_excludes_for_later_pass():
    """Pass 2 may use pass-1 exclusions (bottom option dropped)."""
    class P:
        project_exclusive_mode = True
        min_expected_passes = 2
        max_recommended_passes = 3
        option_questions_per_group = 20
        factor_questions_per_group = 20
        option_questions_per_group_explicit = True
        factor_questions_per_group_explicit = False

    alts = [{"id": i, "alternative_title": f"O{i}"} for i in range(1, 7)]
    facs = [{"id": 10, "factor_title": "F1"}, {"id": 11, "factor_title": "F2"}]
    done = [
        {
            "pass_index": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "rank_order": [1, 2, 3, 4, 5, 6],
            "participant_id": 1,
            "comparison_count": 9,
        },
        {
            "pass_index": 1,
            "group_type": "alternative",
            "criterion_id": 11,
            "rank_order": [1, 2, 3, 4, 5, 6],
            "participant_id": 1,
            "comparison_count": 9,
        },
        {
            "pass_index": 1,
            "group_type": "criteria",
            "criterion_id": None,
            "rank_order": [10, 11],
            "participant_id": 1,
            "comparison_count": 1,
        },
    ]
    out = pick_next_sort_group(project=P(), alternatives=alts, factors=facs, groups=done)
    g = out["group"]
    assert g is not None
    assert g["pass_index"] == 2
    assert sorted(g["item_ids"]) == [1, 2, 3, 4, 5, 6], g["item_ids"]


def _completed_option_pass(pass_index: int) -> dict:
    return {
        "pass_index": pass_index,
        "group_type": "alternative",
        "criterion_id": None,
        "rank_order": [1, 2, 3],
        "item_ids": [1, 2, 3],
        "participant_id": 1,
        "comparison_count": 3,
    }


def test_pick_next_group_allows_one_pass_past_recommended():
    class P:
        project_exclusive_mode = False
        min_expected_passes = 2
        max_recommended_passes = 2

    alts = [
        {"id": 1, "alternative_title": "A"},
        {"id": 2, "alternative_title": "B"},
        {"id": 3, "alternative_title": "C"},
    ]
    done = [_completed_option_pass(1), _completed_option_pass(2)]
    out = pick_next_sort_group(project=P(), alternatives=alts, factors=[], groups=done)
    g = out["group"]
    assert g is not None
    assert g["pass_index"] == 3
    assert out["session_complete"] is False


def test_pick_next_group_stops_after_hard_max():
    class P:
        project_exclusive_mode = False
        min_expected_passes = 2
        max_recommended_passes = 2

    alts = [
        {"id": 1, "alternative_title": "A"},
        {"id": 2, "alternative_title": "B"},
        {"id": 3, "alternative_title": "C"},
    ]
    done = [_completed_option_pass(p) for p in (1, 2, 3)]
    out = pick_next_sort_group(project=P(), alternatives=alts, factors=[], groups=done)
    assert out["group"] is None
    assert out["session_complete"] is True


def test_settings_payloads_match_hard_max_helper():
    class Proj:
        min_expected_passes = 2
        max_recommended_passes = 2
        project_exclusive_mode = False
        participant_influence_mode = "comparisons"
        participant_influence_min_comparisons = 10
        factor_weight_floor_alpha = 0.5
        option_questions_per_group = 20
        factor_questions_per_group = 20
        option_questions_per_group_explicit = False
        factor_questions_per_group_explicit = False
        ranking_mode = "rank_all"
        end_time = None
        disabled = False

    from src.api.app_project_vote_events import _project_settings_payload
    from src.api.app_shared_link_ext_access import _project_settings

    expected = hard_max_passes(2, 2)
    assert expected == 3
    assert _project_settings_payload(Proj())["hard_max_passes"] == expected
    assert _project_settings(Proj())["hard_max_passes"] == expected


def test_validate_package():
    issued = {"client_group_id": "abc", "item_ids": [1, 2, 3]}
    pkg = {
        "client_group_id": "abc",
        "item_ids_initial": [1, 2, 3],
        "rank_order": [2, 1, 3],
        "pairings": [{"winner_id": 2, "loser_id": 1}],
    }
    assert validate_group_package(issued, pkg) is None
    bad = dict(pkg, rank_order=[1, 2])
    assert validate_group_package(issued, bad)


def test_mean_rank_report():
    alts = [{"id": 1, "alternative_title": "A"}, {"id": 2, "alternative_title": "B"}]
    facs = [{"id": 10, "factor_title": "F"}]
    groups = [
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 1,
            "rank_order": [1, 2],
            "comparison_count": 1,
            "pairings": [],
        },
        {
            "participant_id": 2,
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 1,
            "rank_order": [2, 1],
            "comparison_count": 1,
            "pairings": [],
        },
    ]
    report = build_report(
        alternatives=alts,
        factors=facs,
        all_groups=groups,
        participants=[{"id": 1}, {"id": 2}],
        settings={"participant_influence_mode": "comparisons"},
    )
    assert report["option_ranking"]
    assert report["metrics"]["group_count"] == 2
    m = project_metrics(groups, alternatives=alts, factors=facs)
    assert m["comparison_count"] == 2


def test_stability_multi_pass():
    groups = [
        {"group_type": "alternative", "criterion_id": None, "pass_index": 1, "rank_order": [1, 2, 3]},
        {"group_type": "alternative", "criterion_id": None, "pass_index": 2, "rank_order": [1, 2, 3]},
    ]
    s = within_participant_stability(groups)
    assert s > 0.9


class _MultiPassP:
    project_exclusive_mode = False
    min_expected_passes = 2
    max_recommended_passes = 3
    option_questions_per_group = 20
    factor_questions_per_group = 20
    option_questions_per_group_explicit = False
    factor_questions_per_group_explicit = False
    ranking_mode = "rank_all"


def test_required_slots_deterministic_per_seed():
    option_ids = list(range(1, 10))
    a = required_slots_for_pass(pass_index=1, alternative_ids=option_ids, factor_ids=[10], seed=42, option_question_budget=13)
    b = required_slots_for_pass(pass_index=1, alternative_ids=option_ids, factor_ids=[10], seed=42, option_question_budget=13)
    c = required_slots_for_pass(pass_index=1, alternative_ids=option_ids, factor_ids=[10], seed=43, option_question_budget=13)
    assert [(s["group_type"], s["criterion_id"], sorted(s["item_ids"])) for s in a] == [
        (s["group_type"], s["criterion_id"], sorted(s["item_ids"])) for s in b
    ]
    assert [sorted(s["item_ids"]) for s in a] != [sorted(s["item_ids"]) for s in c]


def test_required_slots_single_group_per_channel_at_target_size():
    slots = required_slots_for_pass(
        pass_index=1, alternative_ids=list(range(1, 10)), factor_ids=[10], seed=7, option_question_budget=13
    )
    assert len(slots) == 1
    slot = slots[0]
    assert slot["batch_index"] == 0
    assert len(slot["item_ids"]) == 7  # max items within the 13-question budget
    assert slot["question_budget"] == 13


def test_pass_issues_each_factor_once_with_target_sized_groups():
    """9 options / 5 factors: exactly one group per factor per pass at target size,
    then one factor-comparison group ends the pass. No channel revisits, no splits,
    and different passes sample different subsets."""
    option_ids = list(range(1, 10))
    factor_ids = [10, 11, 12, 13, 14]
    alts = [{"id": i, "alternative_title": f"O{i}"} for i in option_ids]
    facs = [{"id": f, "factor_title": f"F{f}"} for f in factor_ids]
    seed = 1097

    done: list[dict] = []
    issued: list[dict] = []
    for _ in range(40):
        out = pick_next_sort_group(
            project=_MultiPassP(), alternatives=alts, factors=facs, groups=done, seed=seed
        )
        g = out.get("group")
        if g is None:
            break
        issued.append(g)
        done.append({
            "pass_index": g["pass_index"],
            "group_type": g["group_type"],
            "criterion_id": g["criterion_id"],
            "item_ids": list(g["item_ids"]),
            "rank_order": list(g["item_ids"]),
            "comparison_count": int(g["question_budget"] or 0),
        })

    pass_channels: dict[int, dict[tuple, list[dict]]] = {}
    for g in issued:
        per_pass = pass_channels.setdefault(g["pass_index"], {})
        per_pass.setdefault((g["group_type"], g["criterion_id"]), []).append(g)

    for p_index, per_pass in pass_channels.items():
        opt_channels = {k: v for k, v in per_pass.items() if k[0] == "alternative"}
        crit = [v[0] for k, v in per_pass.items() if k[0] == "criteria"]
        # one group per factor, target-sized, no overlap within the pass
        assert set(opt_channels.keys()) == {("alternative", f) for f in factor_ids}
        for channel, gs in opt_channels.items():
            assert len(gs) == 1, (p_index, channel)
            assert len(gs[0]["item_ids"]) == 7
            assert gs[0]["question_budget"] == 13
        # the factor comparison closes the pass (single, sized to the factor list)
        assert len(crit) == 1
        assert len(crit[0]["item_ids"]) == len(factor_ids)
        last = [g for gs in per_pass.values() for g in gs][-1]
        assert last["group_type"] == "criteria"

    # two passes sample different subsets so all options get compared across passes
    def pass_items(p_index):
        return {
            frozenset(g["item_ids"])
            for gs in pass_channels[p_index].values() if gs[0]["group_type"] == "alternative"
            for g in gs
        }

    assert pass_items(1) != pass_items(2)
