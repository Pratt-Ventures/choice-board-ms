COMPARE_PROMPT_MAX_LEN = 280
COMPARE_PROMPT_OPTION_MAX_LEN = 280
COMPARE_PROMPT_FACTOR_MAX_LEN = 200


def normalize_compare_prompt(value: str | None, max_len: int = COMPARE_PROMPT_MAX_LEN) -> str | None:
    if value is None:
        return None
    trimmed = str(value).strip()
    if not trimmed:
        return None
    if len(trimmed) > max_len:
        trimmed = trimmed[:max_len].rstrip()
    return trimmed
