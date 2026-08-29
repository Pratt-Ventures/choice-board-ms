from src.utils.ai.prompts import pairwise_messages
from src.utils.comparison_question import normalize_comparison_question


def test_normalize_comparison_question():
    assert normalize_comparison_question(None) is None
    assert normalize_comparison_question("   ") is None
    assert normalize_comparison_question("  Which option is cheaper?  ") == "Which option is cheaper?"
    assert len(normalize_comparison_question("x" * 250) or "") == 200


def test_pairwise_messages_uses_comparison_question():
    msgs = pairwise_messages(
        problem_title="Pick a vendor",
        problem_description="Choose a supplier",
        left_title="Acme",
        left_description="",
        right_title="Globex",
        right_description="",
        factor_title="Engineering Cost",
        factor_description="Prefer lower cost",
        group_type="alternative",
        comparison_question="Which option has lower Engineering Cost?",
    )
    system = msgs[0]["content"]
    user = msgs[1]["content"]
    assert "Which option has lower Engineering Cost?" in user
    assert "Engineering Cost" in user
    assert "Prefer lower cost" in user
    assert "Which option has lower Engineering Cost?" in user

    fallback = pairwise_messages(
        problem_title="Pick a vendor",
        problem_description="",
        left_title="Acme",
        left_description="",
        right_title="Globex",
        right_description="",
        factor_title="Engineering Cost",
        factor_description="",
        group_type="alternative",
    )
    assert "Engineering Cost" in fallback[1]["content"]
    assert "Which option has lower Engineering Cost?" not in fallback[1]["content"]
