import json
from pathlib import Path

from src.utils.pair_scheduler import (
    PairAnswer,
    RankingTarget,
    SchedulerState,
    choose_orientation,
    select_next_pair,
)

GOLDEN = Path(__file__).parent / "fixtures" / "pair_scheduler_golden.json"


def _winner_fn(kind: str):
    def fn(left: int, right: int, i: int) -> str:
        if kind == "left":
            return "left"
        if kind == "alt":
            return "left" if i % 2 == 0 else "right"
        if kind == "tie-every-3":
            return "tie" if i % 3 == 0 else "left"
        return "left"
    return fn


def test_pair_scheduler_matches_ts_golden():
    cases = json.loads(GOLDEN.read_text())
    assert cases
    for case in cases:
        items = list(case["items"])
        budget = int(case["budget"])
        pass_index = int(case["passIndex"])
        target_raw = case["target"]
        target = RankingTarget(mode=target_raw["mode"], n=target_raw.get("n"))
        choose = _winner_fn(case["winner"])
        state = SchedulerState(
            items=items,
            target=target,
            pass_index=pass_index,
            question_budget=budget,
            answers=[],
            prior_answers=[],
            last_pair=None,
        )
        got = []
        while True:
            pair = select_next_pair(state)
            if pair is None:
                break
            left, right = choose_orientation(
                pair[0], pair[1], [*state.prior_answers, *state.answers], [pass_index, budget, *items]
            )
            choice = choose(left, right, len(got))
            ans = PairAnswer(
                item_a=pair[0],
                item_b=pair[1],
                winner_id=None if choice == "tie" else (left if choice == "left" else right),
                response="tie" if choice == "tie" else "winner",
                presented_left_id=left,
                presented_right_id=right,
                decision_seconds=0,
            )
            state.answers.append(ans)
            state.last_pair = pair
            got.append({"pair": list(pair), "orient": {"left": left, "right": right}, "choice": choice})
        expected = case["sequence"]
        assert len(got) == len(expected), case["name"]
        for i, (g, e) in enumerate(zip(got, expected)):
            assert g["pair"] == e["pair"], (case["name"], i, g, e)
            assert g["orient"] == e["orient"], (case["name"], i, g, e)
            assert g["choice"] == e["choice"], (case["name"], i, g, e)
