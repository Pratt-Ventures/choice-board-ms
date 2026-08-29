from __future__ import annotations

import math
from typing import Any

from ..comparison_question import normalize_comparison_question
from ..compare_prompt import normalize_compare_prompt

# --- quota helpers -----------------------------------------------------------

def ai_vote_threshold(group_size: int) -> int:
    """Combined TIE+SKIP quota before prompt restricts to 1-or-2 only.

    Spec: 20% of group size with minimum 1. Group size is the number of
    items in the sort group (len(item_ids_initial)). Once quota is reached,
    the choice line switches to "Respond with Option 1 or Option 2."

    Quota is per-group, combined TIE+SKIP. Threshold 0 only for n<=0
    (return 0 so caller can disallow abstention entirely).
    """
    try:
        n = int(group_size or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return 0
    ratio = 0.2
    min_q = 1
    try:
        from ...config.config_settings import settings as _s
        ratio = float(getattr(_s, "AI_TIE_SKIP_QUOTA_RATIO", 0.2) or 0.2)
        min_q = int(getattr(_s, "AI_TIE_SKIP_QUOTA_MIN", 1) or 1)
    except Exception:
        pass
    # also try pvf/runtime overrides if present (mirrors config.py pattern)
    try:
        from ...pvf.bindings.pvf_invocation import runtime_settings
        rs = runtime_settings()
        if rs is not None:
            if hasattr(rs, "AI_TIE_SKIP_QUOTA_RATIO"):
                ratio = float(getattr(rs, "AI_TIE_SKIP_QUOTA_RATIO") or ratio)
            if hasattr(rs, "AI_TIE_SKIP_QUOTA_MIN"):
                min_q = int(getattr(rs, "AI_TIE_SKIP_QUOTA_MIN") or min_q)
    except Exception:
        pass
    ratio = max(0.01, min(0.9, float(ratio)))
    min_q = max(1, int(min_q))
    return max(min_q, math.ceil(n * ratio))


# alias for clarity — spec wording
tie_skip_quota = ai_vote_threshold


def combined_abstentions(answers: list[Any] | None) -> int:
    """Count combined skip+tie (inclusive of 'unsure') in a group."""
    if not answers:
        return 0
    cnt = 0
    for a in answers:
        resp = getattr(a, "response", None) if not isinstance(a, dict) else a.get("response")
        if resp is None:
            continue
        r = str(resp).lower()
        if r in ("skipped", "skip", "tie", "unsure"):
            cnt += 1
    return cnt


def quota_reached(group_size: int, abstentions: int) -> bool:
    thresh = ai_vote_threshold(group_size)
    if thresh <= 0:
        return True  # no abstentions allowed for degenerate groups
    return int(abstentions or 0) >= thresh


# --- template resolution + safe formatting -----------------------------------

_DEFAULT_CHOICE_TIE_SKIP = "Respond with 1, 2, TIE or SKIP. Use TIE and SKIP sparingly."
_DEFAULT_CHOICE_STRICT = "Respond with Option 1 or Option 2."

_DEFAULT_SINGLE = (
    "You are an agent being asked for a ranking opinion between the following two options. "
    "Choose the best overall answer based on information provided and your prior knowledge.\n\n"
    "Project Context: {project_title}\n{project_description}\n\n"
    "Option 1: {option1_title}\n{option1_description}\n\n"
    "Option 2: {option2_title}\n{option2_description}\n\n1. {choice_1}\n2. {choice_2}"
)

_DEFAULT_FACTOR_OPTION = (
    "You are an agent being asked for a ranking opinion between the following two options. "
    "This ranking is for a specific factor or perspective. Make a selection based on the factor "
    "and specific question, keeping the factor in context, based on your overall knowledge.\n\n"
    "Project Context: {project_title}\n{project_description}\n\n"
    "Current Factor: {factor_title}\n{factor_description}\n\n{factor_question}\n\n"
    "Option 1: {option1_title}\n{option1_description}\n\n"
    "Option 2: {option2_title}\n{option2_description}\n\n1. {choice_1}\n2. {choice_2}"
)

_DEFAULT_FACTOR_RANKING = (
    "You are an agent being asked for a ranking the importance of two factors being used in a "
    "weighted selection ranking process. Choose the more important factor based on information "
    "provided and your prior knowledge.\n\n"
    "Project Context: {project_title}\n{project_description}\n\n"
    "Factor 1: {factor1_title}\nFactor 1 Question Format: {factor1_question}\nFactor 1 description: {factor1_description}\n\n"
    "Factor 2: {factor2_title}\nFactor 2 Question Format: {factor2_question}\nFactor 2 description: {factor2_description}\n\n1. {choice_1}\n2. {choice_2}"
)


def _get_templates() -> tuple[str, str, str, str, str, str, str, str, str]:
    """Return 9-tuple of templates and choice lines from settings.

    Returns (single_tpl, factor_opt_tpl, factor_rank_tpl,
             choice_tie_skip, choice_strict,
             choice_tie_skip_with_factor, choice_strict_with_factor,
             choice_tie_skip_factors_only, choice_strict_factors_only).
    """
    single = _DEFAULT_SINGLE
    factor_opt = _DEFAULT_FACTOR_OPTION
    factor_rank = _DEFAULT_FACTOR_RANKING
    tie_skip = _DEFAULT_CHOICE_TIE_SKIP
    strict = _DEFAULT_CHOICE_STRICT
    tie_skip_wf = _DEFAULT_CHOICE_TIE_SKIP
    strict_wf = _DEFAULT_CHOICE_STRICT
    tie_skip_fo = _DEFAULT_CHOICE_TIE_SKIP
    strict_fo = _DEFAULT_CHOICE_STRICT
    try:
        from ...config.config_settings import settings as app_s
        single = str(getattr(app_s, "AI_PROMPT_SINGLE_OPTION_TEMPLATE", single) or single)
        factor_opt = str(getattr(app_s, "AI_PROMPT_FACTOR_OPTION_TEMPLATE", factor_opt) or factor_opt)
        factor_rank = str(getattr(app_s, "AI_PROMPT_FACTOR_RANKING_TEMPLATE", factor_rank) or factor_rank)
        tie_skip = str(getattr(app_s, "AI_PROMPT_CHOICE_TIE_SKIP", tie_skip) or tie_skip)
        strict = str(getattr(app_s, "AI_PROMPT_CHOICE_STRICT", strict) or strict)
        tie_skip_wf = str(getattr(app_s, "AI_PROMPT_CHOICE_TIE_SKIP_WITH_FACTOR", "") or "")
        strict_wf = str(getattr(app_s, "AI_PROMPT_CHOICE_STRICT_WITH_FACTOR", "") or "")
        tie_skip_fo = str(getattr(app_s, "AI_PROMPT_CHOICE_TIE_SKIP_FACTORS_ONLY", "") or "")
        strict_fo = str(getattr(app_s, "AI_PROMPT_CHOICE_STRICT_FACTORS_ONLY", "") or "")
        # fallback to legacy if new keys missing/empty (loud warning, no crash)
        if not tie_skip_wf:
            tie_skip_wf = tie_skip
            try:
                from ...pvf.utils import utils_show as _ut
                _ut.show_vars_semi("AI_PROMPT_CHOICE_TIE_SKIP_WITH_FACTOR missing, falling back to TIE_SKIP")
            except Exception:
                pass
        if not strict_wf:
            strict_wf = strict
            try:
                from ...pvf.utils import utils_show as _ut2
                _ut2.show_vars_semi("AI_PROMPT_CHOICE_STRICT_WITH_FACTOR missing, falling back to STRICT")
            except Exception:
                pass
        if not tie_skip_fo:
            tie_skip_fo = tie_skip
            try:
                from ...pvf.utils import utils_show as _ut3
                _ut3.show_vars_semi("AI_PROMPT_CHOICE_TIE_SKIP_FACTORS_ONLY missing, falling back to TIE_SKIP")
            except Exception:
                pass
        if not strict_fo:
            strict_fo = strict
            try:
                from ...pvf.utils import utils_show as _ut4
                _ut4.show_vars_semi("AI_PROMPT_CHOICE_STRICT_FACTORS_ONLY missing, falling back to STRICT")
            except Exception:
                pass
    except Exception:
        pass
    # runtime override (covers pvf invocation startup values if injected)
    try:
        from ...pvf.bindings.pvf_invocation import runtime_settings
        rs = runtime_settings()
        if rs is not None:
            if hasattr(rs, "AI_PROMPT_SINGLE_OPTION_TEMPLATE"):
                v = getattr(rs, "AI_PROMPT_SINGLE_OPTION_TEMPLATE")
                if v:
                    single = str(v)
            if hasattr(rs, "AI_PROMPT_FACTOR_OPTION_TEMPLATE"):
                v = getattr(rs, "AI_PROMPT_FACTOR_OPTION_TEMPLATE")
                if v:
                    factor_opt = str(v)
            if hasattr(rs, "AI_PROMPT_FACTOR_RANKING_TEMPLATE"):
                v = getattr(rs, "AI_PROMPT_FACTOR_RANKING_TEMPLATE")
                if v:
                    factor_rank = str(v)
            if hasattr(rs, "AI_PROMPT_CHOICE_TIE_SKIP"):
                v = getattr(rs, "AI_PROMPT_CHOICE_TIE_SKIP")
                if v:
                    tie_skip = str(v)
            if hasattr(rs, "AI_PROMPT_CHOICE_STRICT"):
                v = getattr(rs, "AI_PROMPT_CHOICE_STRICT")
                if v:
                    strict = str(v)
            # new scenario-specific overrides
            if hasattr(rs, "AI_PROMPT_CHOICE_TIE_SKIP_WITH_FACTOR"):
                v = getattr(rs, "AI_PROMPT_CHOICE_TIE_SKIP_WITH_FACTOR")
                if v:
                    tie_skip_wf = str(v)
            if hasattr(rs, "AI_PROMPT_CHOICE_STRICT_WITH_FACTOR"):
                v = getattr(rs, "AI_PROMPT_CHOICE_STRICT_WITH_FACTOR")
                if v:
                    strict_wf = str(v)
            if hasattr(rs, "AI_PROMPT_CHOICE_TIE_SKIP_FACTORS_ONLY"):
                v = getattr(rs, "AI_PROMPT_CHOICE_TIE_SKIP_FACTORS_ONLY")
                if v:
                    tie_skip_fo = str(v)
            if hasattr(rs, "AI_PROMPT_CHOICE_STRICT_FACTORS_ONLY"):
                v = getattr(rs, "AI_PROMPT_CHOICE_STRICT_FACTORS_ONLY")
                if v:
                    strict_fo = str(v)
            # ensure runtime fallback if still empty
            if not tie_skip_wf:
                tie_skip_wf = tie_skip
            if not strict_wf:
                strict_wf = strict
            if not tie_skip_fo:
                tie_skip_fo = tie_skip
            if not strict_fo:
                strict_fo = strict
    except Exception:
        pass
    # final guarantee: no empty choice lines
    tie_skip_wf = tie_skip_wf or tie_skip
    strict_wf = strict_wf or strict
    tie_skip_fo = tie_skip_fo or tie_skip
    strict_fo = strict_fo or strict
    return single, factor_opt, factor_rank, tie_skip, strict, tie_skip_wf, strict_wf, tie_skip_fo, strict_fo


def _detect_scenario(group_type: str, factor_title: str | None) -> str:
    """Map worker context to scenario enum.

    Returns one of: "single_option", "factor_option", "factor_ranking".
    """
    is_criteria = str(group_type or "").strip().lower() in ("criteria", "factor", "factors")
    if is_criteria:
        return "factor_ranking"
    if factor_title and str(factor_title).strip():
        return "factor_option"
    return "single_option"


def _choice_for(scenario: str, allow_skip_tie: bool, templates: tuple[str, ...]) -> str:
    """Centralized finalization selector: 3 scenarios × 2 states = 6 combinations."""
    # templates is 9-tuple from _get_templates()
    _, _, _, tie_skip, strict, tie_skip_wf, strict_wf, tie_skip_fo, strict_fo = templates
    s = str(scenario or "single_option").strip().lower()
    if s in ("factor_ranking", "criteria", "factors_only", "factors"):
        return tie_skip_fo if allow_skip_tie else strict_fo
    if s in ("factor_option", "with_factor"):
        return tie_skip_wf if allow_skip_tie else strict_wf
    return tie_skip if allow_skip_tie else strict


def get_finalization_prompt(*, scenario: str, threshold_reached: bool | None = None, allow_skip_tie: bool | None = None) -> str:
    """Public helper: get finalization prompt for scenario.

    Either threshold_reached or allow_skip_tie must be supplied; they are inverses.
    threshold_reached = not allow_skip_tie (quota reached => strict).
    """
    if allow_skip_tie is None:
        if threshold_reached is None:
            raise ValueError("get_finalization_prompt requires allow_skip_tie or threshold_reached")
        allow_skip_tie = not bool(threshold_reached)
    else:
        allow_skip_tie = bool(allow_skip_tie)
    templates = _get_templates()
    return _choice_for(scenario, allow_skip_tie, templates)


def _safe_format(template: str, params: dict[str, Any], fallback: str) -> str:
    """Format template with params; on failure log and return fallback formatted with same params."""
    try:
        return template.format(**params)
    except Exception as ex:
        try:
            from ...pvf.utils import utils_show as ut
            ut.show_vars_semi(
                "ai prompt format failed; using fallback",
                error=str(ex) or type(ex).__name__,
                template_preview=str(template)[:300],
                missing_keys=str(sorted(params.keys()))[:400],
            )
        except Exception:
            pass
        try:
            return fallback.format(**params)
        except Exception:
            # ultimate minimal fallback
            try:
                from ...pvf.utils import utils_show as ut2
                ut2.show_vars_semi("ai prompt fallback also failed", error=str(ex)[:200])
            except Exception:
                pass
            # return template raw with best effort
            return fallback


def factor_suggest_messages(*, title: str, description: str) -> list[dict[str, str]]:
    problem_title = (title or "").strip()
    problem_description = (description or "").strip()
    system = (
        "You suggest comparison factors for a decision problem. "
        "Return JSON only, no markdown. "
        "Schema: {\"factors\": [{\"title\": string, \"description\": string}]}. "
        "Produce 5 to 8 distinct factors. Titles are short (2-6 words). "
        "Descriptions are one or two sentences. Do not include polarity, scores, or rankings."
    )
    user = (
        f"Problem title: {problem_title}\n"
        f"Problem description: {problem_description}\n"
        "Suggest the factors that would most help people compare options."
    )
    return [
        {"role": "system", "content": system},
        {"role": "pvf_user", "content": user},
    ]


_DEPRECATED_CHOICE_LINE_WARNED = False


def _sanitize_choice_line(text: str) -> str:
    """Strip and remove internal newlines to preserve ``1. …\\n2. …`` layout."""
    s = str(text or "").strip()
    # Replace any embedded newlines/tabs with single space to keep choice on one line.
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    # Collapse excessive whitespace but preserve single spaces.
    s = " ".join(s.split())
    return s


def _maybe_warn_legacy_choice_line(template: str) -> None:
    global _DEPRECATED_CHOICE_LINE_WARNED
    if "{choice_line}" in template and not _DEPRECATED_CHOICE_LINE_WARNED:
        try:
            from ...pvf.utils import utils_show as ut
            ut.show_vars_semi(
                "ai prompt uses deprecated {choice_line}; migrate to {choice_1}/{choice_2} with '1. {choice_1}\\n2. {choice_2}'",
                template_preview=str(template)[:300],
            )
        except Exception:
            pass
        _DEPRECATED_CHOICE_LINE_WARNED = True


def pairwise_messages(
    *,
    problem_title: str,
    problem_description: str,
    left_title: str,
    left_description: str | None,
    right_title: str,
    right_description: str | None,
    factor_title: str | None,
    factor_description: str | None,
    group_type: str,
    comparison_question: str | None = None,
    allow_skip_tie: bool = True,
    # optional explicit ambient for factor-ranking (when caller has them)
    left_factor_question: str | None = None,
    right_factor_question: str | None = None,
    left_factor_description: str | None = None,
    right_factor_description: str | None = None,
) -> list[dict[str, str]]:
    """Build LLM chat messages for one pairwise vote.

    Randomization is handled by the caller (worker.choose_orientation) which
    decides which stable item maps to Option 1 (left) vs Option 2 (right).
    This function always labels the randomized presentation as Option 1 then
    Option 2, and the caller maps "1"->left / "2"->right back to stable IDs.

    Ambient placeholders are explicit (see config_settings.py):
      single: project_title, project_description, option1_title, option1_description,
              option2_title, option2_description, choice_1, choice_2 (legacy choice_line supported)
      factor-option: + factor_title, factor_description, factor_question
      factor-ranking: project_title, project_description, factor1_title, factor1_question,
                      factor1_description, factor2_title, factor2_question, factor2_description
      Choice lines are rendered as ``1. {choice_1}\\n2. {choice_2}`` on successive lines.
    """
    question = normalize_comparison_question(comparison_question)
    templates = _get_templates()
    single_tpl, factor_opt_tpl, factor_rank_tpl = templates[0], templates[1], templates[2]
    # Centralized scenario-aware finalization selection (6 combinations)
    scenario = _detect_scenario(group_type, factor_title)
    # When factor ranking, override detection to ensure factors_only even if factor_title is also set
    # (group_type == criteria already handled in _detect_scenario)
    selected = _choice_for(scenario, bool(allow_skip_tie), templates)
    sanitized = _sanitize_choice_line(selected)
    choice_1 = sanitized
    choice_2 = sanitized
    # Backward compat: keep {choice_line} populated for custom templates still referencing it.
    choice_line = sanitized
    # Audit log for debugging: scenario + threshold state + preview
    try:
        from ...pvf.utils import utils_show as _ut_audit
        _ut_audit.show_vars_semi(
            "ai pairwise prompt selected",
            scenario=scenario,
            allow_skip_tie=bool(allow_skip_tie),
            group_type=str(group_type),
            choice_preview=sanitized[:120],
        )
    except Exception:
        pass

    is_criteria = str(group_type).strip().lower() in ("criteria", "factor", "factors")

    # ---- criteria / factor-importance ranking ---------------------------------
    if is_criteria:
        # left/right are factors being ranked. Use factor1_* / factor2_* .
        # Caller passes left_title/right_title as factor titles; factor_description/question may be in extra args
        # or left_description/right_description.
        f1_title = str(left_title or "").strip()
        f2_title = str(right_title or "").strip()
        f1_desc = str(left_factor_description if left_factor_description is not None else (left_description or "")).strip()
        f2_desc = str(right_factor_description if right_factor_description is not None else (right_description or "")).strip()
        f1_q = normalize_comparison_question(left_factor_question if left_factor_question is not None else None) or ""
        f2_q = normalize_comparison_question(right_factor_question if right_factor_question is not None else None) or ""
        # Fallback: if no per-factor questions supplied, try factor_title's question (not applicable here)
        _maybe_warn_legacy_choice_line(factor_rank_tpl)
        params = {
            "project_title": str(problem_title or "").strip(),
            "project_description": str(problem_description or "").strip(),
            "factor1_title": f1_title,
            "factor1_question": f1_q,
            "factor1_description": f1_desc,
            "factor2_title": f2_title,
            "factor2_question": f2_q,
            "factor2_description": f2_desc,
            "choice_1": choice_1,
            "choice_2": choice_2,
            "choice_line": choice_line,
        }
        content = _safe_format(factor_rank_tpl, params, _DEFAULT_FACTOR_RANKING.format(**params) if _DEFAULT_FACTOR_RANKING else factor_rank_tpl)
        # keep a tiny system wrapper for provider compatibility; primary instruction lives in user content per spec
        system = "You are one participant in a pairwise comparison. Reply with exactly one token as instructed. Never explain."
        if not allow_skip_tie:
            system = "You are one participant in a pairwise comparison. Reply with exactly one token: 1 or 2 (or Option 1 / Option 2). Never reply TIE or SKIP. Never explain."
        return [
            {"role": "system", "content": system},
            {"role": "pvf_user", "content": content},
        ]

    # ---- factor-specific vs single option comparison --------------------------
    if factor_title:
        _maybe_warn_legacy_choice_line(factor_opt_tpl)
        params = {
            "project_title": str(problem_title or "").strip(),
            "project_description": str(problem_description or "").strip(),
            "factor_title": str(factor_title or "").strip(),
            "factor_description": str(factor_description or "").strip(),
            "factor_question": str(question or "").strip(),
            "option1_title": str(left_title or "").strip(),
            "option1_description": str(left_description or "").strip(),
            "option2_title": str(right_title or "").strip(),
            "option2_description": str(right_description or "").strip(),
            "choice_1": choice_1,
            "choice_2": choice_2,
            "choice_line": choice_line,
        }
        fallback = _DEFAULT_FACTOR_OPTION
        tpl = factor_opt_tpl
        # fallback formatting uses default template directly to guarantee success
        try:
            content_try = tpl.format(**params)
        except Exception as ex:
            try:
                from ...pvf.utils import utils_show as ut
                ut.show_vars_semi("ai prompt factor-option format failed", error=str(ex)[:300])
            except Exception:
                pass
            content_try = _DEFAULT_FACTOR_OPTION.format(**params)
        content = content_try
        system = "You are one participant in a pairwise comparison. Reply with exactly one token as instructed. Never explain."
        if not allow_skip_tie:
            system = "You are one participant in a pairwise comparison. Reply with exactly one token: 1 or 2 (or Option 1 / Option 2). Never reply TIE or SKIP. Never explain."
        return [
            {"role": "system", "content": system},
            {"role": "pvf_user", "content": content},
        ]

    # ---- single factor / overall option comparison ---------------------------
    _maybe_warn_legacy_choice_line(single_tpl)
    params = {
        "project_title": str(problem_title or "").strip(),
        "project_description": str(problem_description or "").strip(),
        "option1_title": str(left_title or "").strip(),
        "option1_description": str(left_description or "").strip(),
        "option2_title": str(right_title or "").strip(),
        "option2_description": str(right_description or "").strip(),
        "choice_1": choice_1,
        "choice_2": choice_2,
        "choice_line": choice_line,
    }
    try:
        content = single_tpl.format(**params)
    except Exception as ex:
        try:
            from ...pvf.utils import utils_show as ut
            ut.show_vars_semi("ai prompt single-option format failed", error=str(ex)[:300])
        except Exception:
            pass
        content = _DEFAULT_SINGLE.format(**params)
    system = "You are one participant in a pairwise comparison. Reply with exactly one token as instructed. Never explain."
    if not allow_skip_tie:
        system = "You are one participant in a pairwise comparison. Reply with exactly one token: 1 or 2 (or Option 1 / Option 2). Never reply TIE or SKIP. Never explain."
    return [
        {"role": "system", "content": system},
        {"role": "pvf_user", "content": content},
    ]


def parse_pairwise_choice(text: str) -> str | None:
    """Parse LLM token to left/right/tie/skipped.

    Accepts: 1 / 2 / Option 1 / Option 2 / LEFT / RIGHT / TIE / SKIP (and synonyms).
    Returns "left" for Option 1, "right" for Option 2, "tie", "skipped", or None (unknown).
    """
    raw = (text or "").strip()
    if not raw:
        return None
    # first token plus full-text checks
    first = raw.split()[0].strip().upper().strip(".,:;\"'`")
    # numeric / option forms
    if first in ("1", "OPTION1", "OPTION_1"):
        return "left"
    if first in ("2", "OPTION2", "OPTION_2"):
        return "right"
    # handle "Option 1" as two tokens — check lower
    lowered = raw.strip().lower()
    if lowered.startswith("option 1") or lowered.startswith("option1") or lowered == "1":
        return "left"
    if lowered.startswith("option 2") or lowered.startswith("option2") or lowered == "2":
        return "right"
    if first in ("LEFT", "L", "WINNER_LEFT", "A"):
        return "left"
    if first in ("RIGHT", "R", "WINNER_RIGHT", "B"):
        return "right"
    if first in ("TIE", "EQUAL", "DRAW"):
        return "tie"
    if first in ("SKIP", "SKIPPED", "UNSURE", "PASS", "ABSTAIN"):
        return "skipped"
    if lowered.startswith("left"):
        return "left"
    if lowered.startswith("right"):
        return "right"
    if lowered.startswith("tie"):
        return "tie"
    if lowered.startswith("skip") or lowered.startswith("unsure") or lowered.startswith("abstain") or lowered.startswith("pass"):
        return "skipped"
    # bare numeric after stripping punctuation
    if first == "1":
        return "left"
    if first == "2":
        return "right"
    return None


def parse_factor_suggestions(payload: Any) -> list[dict[str, str]]:
    rows: list = []
    if isinstance(payload, dict):
        raw = payload.get("factors") or payload.get("suggestions") or []
        rows = raw if isinstance(raw, list) else []
    elif isinstance(payload, list):
        rows = payload
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("factor_title") or "").strip()
        description = str(item.get("description") or item.get("factor_description") or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title[:200], "description": description[:2000]})
        if len(out) >= 8:
            break
    return out


# --- compare_prompt rewrite helpers ------------------------------------------

_DEFAULT_OPTION_REWRITE = (
    "Rewrite title+description as 2-5 word consistent label for pairwise comparison; "
    "no trailing punctuation; preserve meaning; return JSON {\"compare_prompt\": string}"
)
_DEFAULT_FACTOR_REWRITE = (
    "Rewrite as concise question 'Which ...?' <=120 chars; respect polarity (less-is-better vs more-is-better) "
    "and temporal cue; return JSON {\"compare_prompt\": string}"
)


def _rewrite_templates() -> tuple[str, str]:
    opt = _DEFAULT_OPTION_REWRITE
    fac = _DEFAULT_FACTOR_REWRITE
    try:
        from ...config.config_settings import settings as app_s
        opt = str(getattr(app_s, "AI_REWRITE_OPTION_PROMPT", opt) or opt)
        fac = str(getattr(app_s, "AI_REWRITE_FACTOR_PROMPT", fac) or fac)
    except Exception:
        pass
    try:
        from ...pvf.bindings.pvf_invocation import runtime_settings
        rs = runtime_settings()
        if rs is not None:
            if hasattr(rs, "AI_REWRITE_OPTION_PROMPT"):
                v = getattr(rs, "AI_REWRITE_OPTION_PROMPT")
                if v:
                    opt = str(v)
            if hasattr(rs, "AI_REWRITE_FACTOR_PROMPT"):
                v = getattr(rs, "AI_REWRITE_FACTOR_PROMPT")
                if v:
                    fac = str(v)
    except Exception:
        pass
    return opt, fac


def option_rewrite_messages(title: str, description: str | None) -> list[dict[str, str]]:
    opt_tpl, _ = _rewrite_templates()
    user = (
        f"{opt_tpl}\n\nTitle: {(title or '').strip()}\nDescription: {(description or '').strip()}\n"
        "Return JSON only."
    )
    system = "You rewrite option labels for pairwise comparison. Return JSON only, no markdown."
    return [{"role": "system", "content": system}, {"role": "pvf_user", "content": user}]


def factor_rewrite_messages(
    title: str, description: str | None, polarity_positive: bool | None, polarity_note: str | None
) -> list[dict[str, str]]:
    _, fac_tpl = _rewrite_templates()
    pol = "more is better" if polarity_positive else "less is better"
    note = str(polarity_note or "").strip()
    user = (
        f"{fac_tpl}\n\nTitle: {(title or '').strip()}\nDescription: {(description or '').strip()}\n"
        f"Polarity: {pol}\n"
        f"Polarity note: {note}\n"
        "Return JSON only."
    )
    system = "You rewrite factor wording as concise 'Which ...?' question. Return JSON only, no markdown."
    return [{"role": "system", "content": system}, {"role": "pvf_user", "content": user}]


def parse_compare_prompt(payload: Any) -> str | None:
    raw = None
    if isinstance(payload, dict):
        raw = payload.get("compare_prompt") or payload.get("prompt") or payload.get("text") or payload.get("value")
    elif isinstance(payload, str):
        raw = payload
    if raw is None:
        return None
    txt = str(raw).strip()
    if not txt:
        return None
    return normalize_compare_prompt(txt)
