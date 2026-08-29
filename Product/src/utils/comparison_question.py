COMPARISON_QUESTION_MAX_LEN = 200


def normalize_comparison_question(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = str(value).strip()
    if not trimmed:
        return None
    return trimmed[:COMPARISON_QUESTION_MAX_LEN]
