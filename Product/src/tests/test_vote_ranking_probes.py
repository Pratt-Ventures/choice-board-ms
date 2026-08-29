"""Ranked-group Results: mean ranks, top-half stability, confidence, influence."""
from src.utils.vote_ranking import (
    build_report,
    build_personal_submitter_summary,
    build_pivot_detail,
    build_participant_influence_weight_map,
    clamp_factor_weight_floor_alpha,
    factor_weights_from_ranks,
    normalize_participant_influence_mode,
    participant_influence_beta,
    participant_influence_mass,
    project_metrics,
    score_from_mean_rank,
    tied_leader_ids_from_ranking,
    top_half_alignment,
    top_half_dist,
    within_participant_stability,
    DEFAULT_SETTINGS,
)


def _alts():
    return [
        {"id": 1, "alternative_title": "A"},
        {"id": 2, "alternative_title": "B"},
        {"id": 3, "alternative_title": "C"},
    ]


def _facs():
    return [
        {"id": 10, "factor_title": "Cost"},
        {"id": 11, "factor_title": "Quality"},
    ]


def _groups():
    return [
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 1,
            "rank_order": [1, 2, 3],
            "comparison_count": 3,
        },
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 11,
            "pass_index": 1,
            "rank_order": [2, 1, 3],
            "comparison_count": 3,
        },
        {
            "participant_id": 1,
            "group_type": "criteria",
            "criterion_id": None,
            "pass_index": 1,
            "rank_order": [11, 10],
            "comparison_count": 1,
        },
        {
            "participant_id": 2,
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 1,
            "rank_order": [3, 2, 1],
            "comparison_count": 3,
        },
        {
            "participant_id": 2,
            "group_type": "alternative",
            "criterion_id": 11,
            "pass_index": 1,
            "rank_order": [3, 1, 2],
            "comparison_count": 3,
        },
        {
            "participant_id": 2,
            "group_type": "criteria",
            "criterion_id": None,
            "pass_index": 1,
            "rank_order": [10, 11],
            "comparison_count": 1,
        },
    ]


def test_influence_mode_normalize():
    assert normalize_participant_influence_mode("Participants Normalized") == "participants_normalized"
    assert participant_influence_beta("comparisons") == 1.0
    assert participant_influence_beta("participants_normalized") == 0.1


def test_score_normalized_0_1():
    assert score_from_mean_rank(0, 5) == 1.0
    assert score_from_mean_rank(4, 5) == 0.0
    assert abs(score_from_mean_rank(2, 5) - 0.5) < 1e-9
    assert score_from_mean_rank(0, 1) == 1.0


def test_factor_weight_floor_alpha_default_two_clear_ranks():
    """alpha=0.5 → classic 75/25 for two clear ranks (floor = alpha×(n−1))."""
    assert clamp_factor_weight_floor_alpha(None) == 0.5
    assert clamp_factor_weight_floor_alpha(0.01) == 0.1
    assert clamp_factor_weight_floor_alpha(2.0) == 0.9
    w = factor_weights_from_ranks({10: 0.0, 11: 1.0}, floor_alpha=0.5)
    assert abs(w[10] - 0.75) < 1e-9
    assert abs(w[11] - 0.25) < 1e-9


def test_factor_weight_floor_alpha_spread_and_equal():
    clear = {10: 0.0, 11: 1.0, 12: 2.0}
    wide = factor_weights_from_ranks(clear, floor_alpha=0.1)
    mid = factor_weights_from_ranks(clear, floor_alpha=0.5)
    equalish = factor_weights_from_ranks(clear, floor_alpha=0.9)
    # Top/bottom ratio = (1+α)/α decreases as alpha rises
    assert wide[10] / wide[12] > mid[10] / mid[12] > equalish[10] / equalish[12]
    # n-invariant top/bottom at default alpha: always 3×
    two = factor_weights_from_ranks({1: 0.0, 2: 1.0}, floor_alpha=0.5)
    six_ranks = {i: float(i) for i in range(6)}
    six = factor_weights_from_ranks(six_ranks, floor_alpha=0.5)
    assert abs((two[1] / two[2]) - 3.0) < 1e-9
    top_id = min(six_ranks, key=six_ranks.get)
    bot_id = max(six_ranks, key=six_ranks.get)
    assert abs((six[top_id] / six[bot_id]) - 3.0) < 1e-9


def test_build_report_respects_factor_weight_floor_alpha():
    groups = [
        {
            "participant_id": 1,
            "group_type": "criteria",
            "rank_order": [10, 11],
            "comparison_count": 1,
            "pass_index": 1,
        },
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "rank_order": [1, 2, 3],
            "comparison_count": 2,
            "pass_index": 1,
        },
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 11,
            "rank_order": [1, 2, 3],
            "comparison_count": 2,
            "pass_index": 1,
        },
    ]
    report = build_report(
        alternatives=_alts(),
        factors=_facs()[:2],
        all_groups=groups,
        participants=[{"id": 1, "display_name": "Ann", "observation_count": 5}],
        settings={**DEFAULT_SETTINGS, "factor_weight_floor_alpha": 0.1},
    )
    assert abs(report["factor_weight_floor_alpha"] - 0.1) < 1e-9
    weights = report["factor_weights"]
    assert weights
    w10 = float(weights.get(10) or weights.get("10") or 0)
    w11 = float(weights.get(11) or weights.get("11") or 0)
    assert w10 > w11


def test_build_report_mean_ranks_and_scores():
    report = build_report(
        alternatives=_alts(),
        factors=_facs(),
        all_groups=_groups(),
        participants=[
            {"id": 1, "display_name": "Ann", "observation_count": 7},
            {"id": 2, "display_name": "Bob", "observation_count": 7},
        ],
        settings={**DEFAULT_SETTINGS, "participant_influence_mode": "comparisons"},
    )
    assert report["option_ranking"]
    assert report["option_ranking_equal"]
    assert report["factor_ranking"]
    assert report["metrics"]["group_count"] == 6
    assert report["participant_influence_mode"] == "comparisons"
    assert report["dispersion"]
    assert "unique_leaders" in report["dispersion"]
    # scores must be 0–1 (never rank-distance like 4.0)
    for row in report["option_ranking"]:
        assert 0.0 <= float(row["score"]) <= 1.0
    for row in report["factor_ranking"]:
        assert 0.0 <= float(row["score"]) <= 1.0
        assert "normalizedWeight" in row
    # legacy share shape
    assert report["results"]["importance_adjusted"]
    assert report["results"]["leader"]
    # participant aliases
    p0 = report["participants"][0]
    assert p0.get("ranking") is not None
    assert p0.get("leader") is not None or p0.get("option_ranking")


def test_influence_weight_map_and_mass():
    wm = build_participant_influence_weight_map(_groups(), "participants_normalized", 10)
    assert 1 in wm and 2 in wm
    # mass = w * n (not w * n^β again)
    n1 = 7
    mass = participant_influence_mass(n1, wm[1], "participants_normalized")
    assert mass == wm[1] * n1


def test_influence_balanced_mass_increases_with_n():
    # balanced β=0.5 → mass ≈ sqrt(n) when n ≥ floor
    w_map_small = build_participant_influence_weight_map(
        [{"participant_id": 1, "comparison_count": 10}], "balanced", 10
    )
    w_map_big = build_participant_influence_weight_map(
        [{"participant_id": 1, "comparison_count": 40}], "balanced", 10
    )
    m_small = participant_influence_mass(10, w_map_small[1], "balanced")
    m_big = participant_influence_mass(40, w_map_big[1], "balanced")
    assert m_big > m_small


def test_pivot_detail_participant():
    detail = build_pivot_detail(
        alternatives=_alts(),
        factors=_facs(),
        all_groups=_groups(),
        participants=[{"id": 1, "display_name": "Ann"}],
        primary_axis="participants",
        participant_id=1,
    )
    assert detail["option_ranking"] is not None
    assert "metrics" in detail


def test_pivot_detail_honors_factor_filter_for_participant():
    """Participant detail under a factor uses that factor's ranks, not overall."""
    detail = build_pivot_detail(
        alternatives=_alts(),
        factors=_facs(),
        all_groups=_groups(),
        participants=[
            {"id": 1, "display_name": "Ann"},
            {"id": 2, "display_name": "Bob"},
        ],
        primary_axis="participants",
        participant_id=1,
        factor_id=11,  # Quality: p1 order [2, 1, 3]
    )
    ids = [row["id"] for row in detail["option_ranking"]]
    assert ids == [2, 1, 3], ids
    leader = (detail["participants"][0].get("leader") or {})
    assert int(leader.get("id") or 0) == 2


def test_pivot_detail_factor_axis_uses_per_participant_factor_leaders():
    detail = build_pivot_detail(
        alternatives=_alts(),
        factors=_facs(),
        all_groups=_groups(),
        participants=[
            {"id": 1, "display_name": "Ann"},
            {"id": 2, "display_name": "Bob"},
        ],
        primary_axis="factors",
        factor_id=10,  # Cost: p1 [1,2,3], p2 [3,2,1]
    )
    leaders = {
        int(p["id"]): int((p.get("leader") or {}).get("id") or 0)
        for p in detail["participants"]
    }
    assert leaders[1] == 1
    assert leaders[2] == 3
    # filtering to option 1 keeps only Ann
    detail_f = build_pivot_detail(
        alternatives=_alts(),
        factors=_facs(),
        all_groups=_groups(),
        participants=[
            {"id": 1, "display_name": "Ann"},
            {"id": 2, "display_name": "Bob"},
        ],
        primary_axis="factors",
        factor_id=10,
        alternative_id=1,
    )
    assert [int(p["id"]) for p in detail_f["participants"]] == [1]


def test_equal_weight_perfect_reverse_factors_all_tie_for_first():
    """F1 = 1..5 and F2 = 5..1 with equal weights → every option ties for #1."""
    alts = [{"id": i, "alternative_title": f"O{i}"} for i in range(1, 6)]
    facs = [{"id": 10, "factor_title": "F1"}, {"id": 11, "factor_title": "F2"}]
    fwd = [1, 2, 3, 4, 5]
    rev = [5, 4, 3, 2, 1]
    groups = [
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 1,
            "rank_order": fwd,
            "comparison_count": 4,
        },
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 11,
            "pass_index": 1,
            "rank_order": rev,
            "comparison_count": 4,
        },
        {
            "participant_id": 1,
            "group_type": "criteria",
            "criterion_id": None,
            "pass_index": 1,
            "rank_order": [10, 11],
            "comparison_count": 1,
        },
    ]
    report = build_report(
        alternatives=alts,
        factors=facs,
        all_groups=groups,
        participants=[{"id": 1}],
        settings={**DEFAULT_SETTINGS, "participant_influence_mode": "comparisons"},
    )
    eq = report["participants"][0]["option_ranking_equal"]
    assert len(eq) == 5
    scores = [float(r["score"]) for r in eq]
    assert max(scores) - min(scores) < 0.28
    assert all(0.28 <= s <= 0.72 for s in scores)


def test_report_participant_option_ranks_by_factor_for_leader_counts():
    """Leader concentration under a factor must use option_ranks_by_factor #1s."""
    report = build_report(
        alternatives=_alts(),
        factors=_facs(),
        all_groups=_groups(),
        participants=[
            {"id": 1, "display_name": "Ann"},
            {"id": 2, "display_name": "Bob"},
        ],
        settings={**DEFAULT_SETTINGS, "participant_influence_mode": "comparisons"},
    )
    # Under Quality (11): Ann #1=B(2), Bob #1=C(3) — only those two leaders
    counts: dict[int, int] = {}
    for p in report["participants"]:
        ranks = (p.get("option_ranks_by_factor") or {}).get(11) or (p.get("option_ranks_by_factor") or {}).get("11")
        assert ranks, p
        leader_id = min(ranks.keys(), key=lambda k: (float(ranks[k]), int(k)))
        counts[int(leader_id)] = counts.get(int(leader_id), 0) + 1
    assert counts.get(2) == 1
    assert counts.get(3) == 1
    assert counts.get(1, 0) == 0
    # Group mean ranks under Quality may differ from #1 majority — concentration uses #1s only
    assert 11 in report["by_factor"] or "11" in report["by_factor"]


def test_project_metrics_keys_and_ranges():
    m = project_metrics(_groups(), alternatives=_alts(), factors=_facs())
    for k in (
        "stability", "confidence", "agreement", "completion",
        "group_count", "multi_pass", "depth", "factor_divergence",
        "stability_basis",
    ):
        assert k in m
    for k in ("stability", "confidence", "agreement", "multi_pass", "completion", "depth", "factor_divergence"):
        assert 0.0 <= float(m[k]) <= 1.0


def test_factor_divergence_high_when_factors_disagree():
    from src.utils.vote_ranking import factor_option_divergence
    # opposite orderings under two factors → ρ = −1 → divergence = 1
    d = factor_option_divergence({
        10: {1: 0.0, 2: 1.0, 3: 2.0},
        11: {1: 2.0, 2: 1.0, 3: 0.0},
    })
    assert d > 0.9


def test_factor_divergence_low_when_factors_agree():
    from src.utils.vote_ranking import factor_option_divergence
    d = factor_option_divergence({
        10: {1: 0.0, 2: 1.0, 3: 2.0},
        11: {1: 0.0, 2: 1.0, 3: 2.0},
    })
    assert d < 0.05


def test_stability_not_from_cross_factor_within_person():
    """One participant with opposing factor lists must not get stability from cross-factor compare."""
    groups = [
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 1,
            "rank_order": [1, 2, 3],
            "comparison_count": 3,
        },
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 11,
            "pass_index": 1,
            "rank_order": [3, 2, 1],
            "comparison_count": 3,
        },
    ]
    m = project_metrics(groups, alternatives=_alts(), factors=_facs())
    # no multi-pass, no peers → multi_pass 0; stability basis none or multi_pass 0
    assert m["multi_pass"] == 0.0
    assert m["factor_divergence"] > 0.4


def test_top_half_alignment_high_when_same_leaders():
    bundles = [
        {"overall_option_ranks": {1: 0.0, 2: 1.0, 3: 2.0, 4: 3.0}},
        {"overall_option_ranks": {1: 0.0, 2: 1.0, 3: 2.5, 4: 3.0}},
    ]
    s = top_half_alignment(bundles, fraction=0.5)
    assert s > 0.7


def test_top_half_alignment_low_when_opposite():
    bundles = [
        {"overall_option_ranks": {1: 0.0, 2: 1.0, 3: 2.0, 4: 3.0}},
        {"overall_option_ranks": {4: 0.0, 3: 1.0, 2: 2.0, 1: 3.0}},
    ]
    s = top_half_alignment(bundles, fraction=0.5)
    assert s < 0.5


def test_top_half_dist_keeps_half():
    ranks = {1: 0.0, 2: 1.0, 3: 2.0, 4: 3.0}
    d = top_half_dist(ranks, 0.5)
    assert set(d.keys()) == {1, 2}
    assert abs(sum(d.values()) - 1.0) < 1e-9


def test_stability_multi_pass_within():
    groups = [
        {"group_type": "alternative", "criterion_id": None, "pass_index": 1, "rank_order": [1, 2, 3]},
        {"group_type": "alternative", "criterion_id": None, "pass_index": 2, "rank_order": [1, 2, 3]},
    ]
    s = within_participant_stability(groups)
    assert s > 0.9


def test_aligned_voters_high_stability_confidence():
    """Two voters with identical full rankings → high stability & confidence."""
    groups = []
    for pid in (1, 2):
        groups.extend([
            {
                "participant_id": pid,
                "group_type": "alternative",
                "criterion_id": 10,
                "pass_index": 1,
                "rank_order": [1, 2, 3],
                "comparison_count": 3,
            },
            {
                "participant_id": pid,
                "group_type": "alternative",
                "criterion_id": 11,
                "pass_index": 1,
                "rank_order": [1, 2, 3],
                "comparison_count": 3,
            },
            {
                "participant_id": pid,
                "group_type": "criteria",
                "criterion_id": None,
                "pass_index": 1,
                "rank_order": [10, 11],
                "comparison_count": 1,
            },
        ])
    m = project_metrics(groups, alternatives=_alts(), factors=_facs())
    assert m["stability"] > 0.85
    assert m["agreement"] > 0.85
    assert m["confidence"] > 0.5


def test_factor_ranking_keeps_options_without_data_trailing():
    """A factor whose sort groups never covered an option still lists it (unranked)."""
    alts = [
        {"id": 1, "alternative_title": "A"},
        {"id": 2, "alternative_title": "B"},
        {"id": 3, "alternative_title": "C"},
    ]
    facs = [{"id": 10, "factor_title": "Cost"}, {"id": 11, "factor_title": "Quality"}]
    groups = [
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 10,
            "pass_index": 1,
            "rank_order": [1, 2, 3],
            "comparison_count": 3,
        },
        # Quality never ranked option 3
        {
            "participant_id": 1,
            "group_type": "alternative",
            "criterion_id": 11,
            "pass_index": 1,
            "rank_order": [2, 1],
            "comparison_count": 1,
        },
        {
            "participant_id": 1,
            "group_type": "criteria",
            "criterion_id": None,
            "pass_index": 1,
            "rank_order": [11, 10],
            "comparison_count": 1,
        },
    ]
    report = build_report(
        alternatives=alts,
        factors=facs,
        all_groups=groups,
        participants=[{"id": 1, "display_name": "Ann"}],
        settings={**DEFAULT_SETTINGS, "participant_influence_mode": "comparisons"},
    )
    f2 = report["by_factor"][11]
    ids = [row["id"] for row in f2]
    assert ids == [2, 1, 3], ids  # ranked rows first, unranked option trails
    assert f2[0]["mean_rank"] is not None
    assert f2[2]["mean_rank"] is None
    assert f2[2]["score"] == 0
    assert f2[2]["data_points"] == 0
    # overall ranking: option 3 has data via Cost → fully ranked, all three present
    overall = report["option_ranking"]
    assert [row["id"] for row in overall] == [2, 1, 3]
    assert all(row["mean_rank"] is not None for row in overall)
    # pivot rollups survive the unranked row (numeric rank required)
    by_alt = report["pivot"]["by_alternative"]
    assert [row["id"] for row in by_alt] == [2, 1, 3]
    assert by_alt[2]["rank"] == 3
    assert by_alt[2]["leader_count"] == 0


def test_personal_submitter_summary_mode_and_factor_weights():
    personal_groups = [g for g in _groups() if g["participant_id"] == 1]
    summary = build_personal_submitter_summary(
        alternatives=_alts(),
        factors=_facs(),
        groups=personal_groups,
        exclusive_mode=False,
        settings={**DEFAULT_SETTINGS, "ranking_mode": "find_best"},
    )
    assert summary["ranking_mode"] == "find_best"
    assert summary["top_n"] == 1
    assert "confidence" in summary
    assert "participants" not in summary
    assert "dispersion" not in summary
    board = summary["alternative_leaderboard"]
    assert board
    assert "score" in board[0]
    assert board[0].get("rank_ci95") or board[0].get("expected_rank") is not None
    sd = board[0].get("rank_sd")
    assert sd is not None and float(sd) >= 0.0
    factors = summary["factor_leaderboard"]
    assert len(factors) >= 2
    assert any(
        row.get("weight") is not None or row.get("normalizedWeight") is not None
        for row in factors
    )


def test_ranking_stays_empty_without_any_rank_data():
    report = build_report(
        alternatives=_alts(),
        factors=_facs(),
        all_groups=[],
        participants=[],
        settings=DEFAULT_SETTINGS,
    )
    assert report["option_ranking"] == []
    assert report["option_ranking_equal"] == []
    assert report["factor_ranking"] == []
    assert report["by_factor"] == {}
    assert not report["results"]["leader"]
