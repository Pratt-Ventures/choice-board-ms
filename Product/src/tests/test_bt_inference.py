"""Hierarchical BT + Laplace: synthetic recovery, ties/skip, cache, legacy groups."""
from src.utils.bt_inference.cache import clear as clear_bt_cache
from src.utils.bt_inference import laplace as bt_laplace
from src.utils.bt_inference.laplace import reset_fit_calls
from src.utils.bt_inference.observations import extract_observations
from src.utils.bt_inference.ranks import posterior_ranks, rank_summary
from src.utils.vote_ranking import build_report


def setup_function(_fn=None):
    clear_bt_cache()
    reset_fit_calls()


def _alts(n=4):
    return [{"id": i, "alternative_title": chr(64 + i)} for i in range(1, n + 1)]


def _facs():
    return [
        {"id": 10, "factor_title": "Cost"},
        {"id": 11, "factor_title": "Quality"},
    ]


def _adjacent(order):
    return [{"winner_id": a, "loser_id": b, "response": "winner"} for a, b in zip(order, order[1:])]


def _group(pid, order, *, fid=None, gtype="alternative", extra_pairs=None, status="complete", gid=None):
    pairs = list(extra_pairs) if extra_pairs is not None else _adjacent(order)
    return {
        "id": gid,
        "participant_id": pid,
        "group_type": gtype,
        "criterion_id": fid,
        "pass_index": 1,
        "rank_order": order,
        "pairings": pairs,
        "comparison_count": len(pairs),
        "status": status,
    }


def test_posterior_ranks_and_summary_strong_order():
    import numpy as np

    scores = np.array([[4.0, 2.0, 0.0]] * 50)
    ranks = posterior_ranks(scores)
    assert ranks.shape == (50, 3)
    assert (ranks[:, 0] == 1).all()
    summary = rank_summary(scores, top_n=1)
    by_item = {s["item"]: s for s in summary}
    assert by_item[0]["rank"] == 1
    assert by_item[0]["p_best"] == 1.0
    assert by_item[2]["p_best"] == 0.0


def test_rank_summary_exposes_rank_sd():
    import numpy as np

    rng = np.random.default_rng(7)
    scores = np.column_stack([
        np.full(400, 6.0),
        2.0 + rng.normal(0.0, 1.0, 400),
        -2.0 + rng.normal(0.0, 1.0, 400),
    ])
    summary = rank_summary(scores, top_n=1)
    by_item = {s["item"]: s for s in summary}
    for row in summary:
        assert row["rank_sd"] >= 0.0
    # dominant item always ranks #1 → near-zero spread; coin-flip pair spreads wide
    assert by_item[0]["rank_sd"] < 0.05
    assert by_item[0]["rank_sd"] < by_item[1]["rank_sd"]


def test_strong_winner_high_p_best():
    order = [1, 2, 3, 4]
    pairs = [
        {"winner_id": 1, "loser_id": j, "response": "winner"}
        for j in (2, 3, 4)
    ] + [
        {"winner_id": 2, "loser_id": 3, "response": "winner"},
        {"winner_id": 2, "loser_id": 4, "response": "winner"},
        {"winner_id": 3, "loser_id": 4, "response": "winner"},
    ]
    groups = [_group(1, order, fid=None, extra_pairs=pairs)]
    report = build_report(
        alternatives=_alts(4),
        factors=[],
        all_groups=groups,
        participants=[{"id": 1}],
        settings={"bt_n_samples": 400, "ranking_mode": "find_best"},
    )
    ranking = report["option_ranking"]
    assert ranking[0]["id"] == 1
    assert float(ranking[0]["p_best"]) > 0.7
    assert 0.0 <= float(ranking[0]["score"]) <= 1.0
    assert "expected_rank" in ranking[0]
    assert "rank_ci95" in ranking[0]
    sds = {int(r["id"]): float(r["rank_sd"]) for r in ranking}
    assert all(0.0 <= sd <= len(ranking) for sd in sds.values())
    # clear winner hugs rank 1 more tightly than the mid-pack items
    assert sds[1] < sds[2] and sds[1] < sds[3]
    assert report["top_n"] == 1
    assert report["engine"] == "hierarchical_bt_laplace"


def test_tied_leaders_broad_uncertainty():
    pairs = [
        {"winner_id": 1, "loser_id": 3, "response": "winner"},
        {"winner_id": 2, "loser_id": 3, "response": "winner"},
        {"winner_id": 1, "loser_id": 2, "response": "tie"},
        {"winner_id": 3, "loser_id": 4, "response": "winner"},
    ]
    groups = [_group(1, [1, 2, 3, 4], extra_pairs=pairs)]
    report = build_report(
        alternatives=_alts(4),
        factors=[],
        all_groups=groups,
        participants=[{"id": 1}],
        settings={"bt_n_samples": 400, "ranking_mode": "find_best"},
    )
    top = report["option_ranking"][:2]
    ids = {int(r["id"]) for r in top}
    assert 1 in ids and 2 in ids
    assert max(float(r["p_best"]) for r in top) < 0.9


def test_clear_top3_vs_uncertain_boundary():
    # 1,2,3 clearly above 4,5; 3 vs 4 is the close call
    pairs = []
    for w, l in ((1, 4), (1, 5), (2, 4), (2, 5), (3, 5), (1, 2), (2, 3), (3, 4), (4, 5)):
        pairs.append({"winner_id": w, "loser_id": l, "response": "winner"})
    groups = [_group(1, [1, 2, 3, 4, 5], extra_pairs=pairs)]
    report = build_report(
        alternatives=_alts(5),
        factors=[],
        all_groups=groups,
        participants=[{"id": 1}],
        settings={"bt_n_samples": 400, "ranking_mode": "find_top_3"},
    )
    by_id = {int(r["id"]): r for r in report["option_ranking"]}
    assert float(by_id[1]["p_top_n"]) > 0.8
    assert float(by_id[5]["p_top_n"]) < 0.4
    assert report["top_n"] == 3


def test_polarized_participants_not_labeled_unreliable():
    g1 = _group(1, [1, 2, 3, 4], fid=None, gid=1)
    g2 = _group(2, [4, 3, 2, 1], fid=None, gid=2)
    report = build_report(
        alternatives=_alts(4),
        factors=[],
        all_groups=[g1, g2],
        participants=[{"id": 1}, {"id": 2}],
        settings={"bt_n_samples": 400, "ranking_mode": "find_best"},
    )
    lapse = report["diagnostics"].get("lapse")
    assert lapse is None or float(lapse) < 0.25
    p_bests = [float(r["p_best"]) for r in report["option_ranking"]]
    assert max(p_bests) < 0.85
    assert report["coherence"]["directional"] < 0.85


def test_important_but_flat_factor_modest_leverage():
    groups = [
        _group(1, [1, 2, 3], fid=10, gid=1),
        _group(
            1,
            [1, 2, 3],
            fid=11,
            gid=2,
            extra_pairs=[
                {"winner_id": 1, "loser_id": 2, "response": "tie"},
                {"winner_id": 2, "loser_id": 3, "response": "tie"},
                {"winner_id": 1, "loser_id": 3, "response": "tie"},
            ],
        ),
        _group(1, [10, 11], gtype="criteria", gid=3),
    ]
    report = build_report(
        alternatives=_alts(3),
        factors=_facs(),
        all_groups=groups,
        participants=[{"id": 1}],
        settings={"bt_n_samples": 300},
    )
    by_id = {int(r["id"]): r for r in report["factor_ranking"]}
    assert float(by_id[10].get("normalizedWeight") or by_id[10].get("weight") or 0) > float(
        by_id[11].get("normalizedWeight") or by_id[11].get("weight") or 0
    )
    assert float(by_id[11].get("discrimination") or 0) <= float(by_id[10].get("discrimination") or 1)
    if by_id[11].get("leverage") is not None:
        assert float(by_id[11]["leverage"]) < 0.7


def test_ties_unsure_skip_handling():
    pairs = [
        {"winner_id": 1, "loser_id": 2, "response": "winner"},
        {"winner_id": 1, "loser_id": 3, "response": "tie"},
        {"winner_id": 2, "loser_id": 3, "response": "unsure"},
        {"winner_id": 2, "loser_id": 4, "response": "skipped"},
        {"winner_id": 1, "loser_id": 4, "response": "skip"},
    ]
    obs = extract_observations([_group(1, [1, 2, 3, 4], extra_pairs=pairs)])
    responses = {o.response for o in obs}
    assert "unsure" not in responses
    assert "skipped" not in responses
    assert "skip" not in responses
    assert any(o.y == 0.5 for o in obs)
    assert any(o.y == 1.0 for o in obs)
    report = build_report(
        alternatives=_alts(4),
        factors=[],
        all_groups=[_group(1, [1, 2, 3, 4], extra_pairs=pairs)],
        participants=[{"id": 1}],
        settings={"bt_n_samples": 200},
    )
    assert report["option_ranking"][0]["id"] == 1


def test_in_progress_pairings_included():
    complete = _group(1, [1, 2, 3], extra_pairs=[
        {"winner_id": 1, "loser_id": 2, "response": "winner"},
    ], status="complete", gid=1)
    progress = _group(2, [3, 2, 1], extra_pairs=[
        {"winner_id": 3, "loser_id": 1, "response": "winner"},
        {"winner_id": 3, "loser_id": 2, "response": "winner"},
    ], status="in_progress", gid=2)
    report = build_report(
        alternatives=_alts(3),
        factors=[],
        all_groups=[complete, progress],
        participants=[{"id": 1}, {"id": 2}],
        settings={"bt_n_samples": 300},
    )
    ids = [int(r["id"]) for r in report["option_ranking"]]
    assert 3 in ids
    assert report["diagnostics"]["pairings_used"] >= 3


def test_cache_hit_does_not_recompute():
    groups = [_group(1, [1, 2, 3])]
    kwargs = dict(
        alternatives=_alts(3),
        factors=[],
        all_groups=groups,
        participants=[{"id": 1}],
        settings={"bt_n_samples": 120},
    )
    reset_fit_calls()
    clear_bt_cache()
    a = build_report(**kwargs)
    calls_after_first = bt_laplace.FIT_CALLS
    assert calls_after_first >= 1
    b = build_report(**kwargs)
    assert bt_laplace.FIT_CALLS == calls_after_first
    assert b["diagnostics"].get("cache_hit") is True
    assert [r["id"] for r in a["option_ranking"]] == [r["id"] for r in b["option_ranking"]]


def test_legacy_rank_order_only_does_not_crash():
    groups = [{
        "participant_id": 1,
        "group_type": "alternative",
        "criterion_id": None,
        "pass_index": 1,
        "rank_order": [3, 1, 2],
        "pairings": [],
        "comparison_count": 2,
    }]
    report = build_report(
        alternatives=_alts(3),
        factors=[],
        all_groups=groups,
        participants=[{"id": 1}],
        settings={"bt_n_samples": 200},
    )
    assert report["option_ranking"]
    assert report["option_ranking"][0]["id"] == 3
    assert report["diagnostics"]["legacy_rank_only_groups"] >= 1


def test_report_adds_posterior_fields():
    report = build_report(
        alternatives=_alts(3),
        factors=[],
        all_groups=[_group(1, [1, 2, 3])],
        participants=[{"id": 1}],
        settings={"bt_n_samples": 150, "ranking_mode": "rank_all"},
    )
    row = report["option_ranking"][0]
    for key in ("p_best", "p_top_n", "rank_ci95", "expected_rank", "pairwise_win_strength"):
        assert key in row
    assert "coherence" in report
    assert "directional" in report["coherence"]
    assert "expected_pair_agreement" in report["coherence"]
    assert "posterior_stability" in report
    assert "same_winner_repeat_probability" in report["posterior_stability"]
    assert "same_top_n_repeat_probability" in report["posterior_stability"]
    assert report.get("engine") == "hierarchical_bt_laplace"
    assert report.get("ranking_mode") == "rank_all"
    assert "diagnostics" in report
    assert report["diagnostics"]["model"] == "hierarchical_bt_laplace"
