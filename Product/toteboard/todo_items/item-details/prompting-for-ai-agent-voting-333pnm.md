# Prompting for AI agent voting

## Short Description
### user
Change the default prompting for AI voting to use choice_1 and choice_2 rather than choice_line. This allows more precise presentation. Then adjust the prompts so they are shown in successive lines with clear 1. and 2. prefixes.
[comment: created 2026-08-21T22:10:36.547Z | id prompting-for-ai-agent-voting-333pnm]

## Expanded Description
### agent
Migrate the default AI agent voting prompt from a single `choice_line` placeholder to distinct `choice_1` and `choice_2` placeholders to enable more precise, per-choice presentation control. Update the default prompt template(s) and rendering logic to display the two choices on successive lines with explicit `1.` and `2.` prefixes for unambiguous selection. Scope is limited to prompting/presentation; no changes to toteboard/board storage, persistence, or voting tally logic.

- Scope: Locate default AI voting prompt template(s)/config using `choice_line` and replace with `choice_1`/`choice_2`; update prompt assembly to emit `1. {choice_1}` and `2. {choice_2}` on consecutive lines.
- Scope: Update any docs, examples, or tests referencing `choice_line` and verify rendered prompt output; no file/queue/toteboard changes.
- Key consideration: Backward compatibility for existing/overridden prompts still referencing `choice_line` — deprecate vs. fallback alias/dual-support during transition.
- Key consideration: Consistent formatting, escaping/truncation, and injection safety for choice content across LLM providers; preserve line breaks/prefixes.
- Open question: Whether prefix style (`1.`/`2.` vs `1:`) and line separation should be hard-coded or made configurable, and if >2-choice variants need future-proofing.
[comment: expand completed 2026-08-21T22:11:03.358Z | via executor-opencode | entryId e-20260821-0001 | artifacts: ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-10-36-587Z-expand-4h3xyu.request.md, ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-10-36-587Z-expand-4h3xyu.response.md, ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-10-36-587Z-expand-4h3xyu.trace.log, ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-10-36-587Z-expand-4h3xyu.result.json]


## Plan
### agent
Building your AI voting prompt plan — mapping the current template and scoping the migration to per-choice placeholders.**Summary:** Migrate AI voting prompting from single `{choice_line}` to dual `{choice_1}`/`{choice_2}` with explicit `1.`/`2.` prefixed successive lines. Scope is prompting/presentation only — no toteboard/board, persistence, or tally logic. Core touchpoints are `src/config/config_settings.py:28-54` (3 templates + 2 choice lines) and `src/utils/ai/prompts.py:79-337` (`_DEFAULT_*`, `_get_templates()`, `pairwise_messages()`), plus `docs_examples/AI_PARTICIPANT_README.MD:43-152` and `src/tests/test_ai_agents.py`.

**Implementation Steps:**
1.  **Inventory & audit (read-only check):** Confirm all `choice_line` occurrences via grep: `src/config/config_settings.py:38,41,47,53`, `src/utils/ai/prompts.py:87,97,106,233,240,265,289,320`, `docs_examples/AI_PARTICIPANT_README.MD:79,84,89,91,112,133,151`. Verify no queue/board usage.
2.  **Define `choice_1`/`choice_2` semantics:** Decide source of per-choice strings. Option: keep existing `AI_PROMPT_CHOICE_TIE_SKIP`/`AI_PROMPT_CHOICE_STRICT` as whole sentences and split/duplicate into `choice_1`/`choice_2` at render; vs. introduce new env vars `AI_PROMPT_CHOICE_1_TIE_SKIP` etc. (see trade-offs). Minimal path: `choice_1 = tie_skip_or_strict_variant_for_1`, `choice_2 = counterpart` (e.g., `"1. Respond with 1, TIE or SKIP"` vs generic sentence duplicated — requires product decision).
3.  **Update `src/config/config_settings.py:28-54`:** Replace `AI_PROMPT_*_TEMPLATE` defaults to end with `1. {choice_1}\n2. {choice_2}` instead of `{choice_line}`; update placeholder comments (`single: {project_title} ... {choice_1} {choice_2}`); add new `AI_PROMPT_CHOICE_1`/`AI_PROMPT_CHOICE_2` or derive logic (if splitting). Keep env override via `environ.get()`. Bump `VERSION`.
4.  **Update `src/utils/ai/prompts.py:79-107`:** Mirror defaults `_DEFAULT_SINGLE/_FACTOR_OPTION/_FACTOR_RANKING` to `...1. {choice_1}\n2. {choice_2}`. Optionally add `_DEFAULT_CHOICE_1_TIE_SKIP` etc. or keep two-line generation in `_get_templates`.
5.  **Update `src/utils/ai/prompts.py:110-337` rendering:** Extend `_get_templates() -> tuple[str,str,str,str,str]` to return `choice_1_tie_skip, choice_1_strict, choice_2...` or keep 2 choice lines and compute `choice_1, choice_2 = _choice_pair(allow_skip_tie)`. In `pairwise_messages()` replace `choice_line = tie_skip_line if allow_skip_tie else strict_line` (`src/utils/ai/prompts.py:240`) with `choice_1/choice_2` pair and params `{"choice_1":..., "choice_2":...}` for all three branches (criteria `src/utils/ai/prompts.py:256`, factor-option `src/utils/ai/prompts.py:279`, single `src/utils/ai/prompts.py:312`). Implement fallback: if template still contains `{choice_line}`, inject legacy combined line and log deprecation via `utils_show`; if new template missing `{choice_1/2}`, inject via `_safe_format` fallback.
6.  **Injection/formatting safety:** Ensure `choice_1/choice_2` strings are stripped, no newlines injected by user content; `pairwise_messages` preserves `\n` between `1.` and `2.` for all LLM providers (tested against `openai`/`opencode_go`); reuse `_safe_format` (`src/utils/ai/prompts.py:156`) for both legacy and new placeholders.
7.  **Docs:** Update `docs_examples/AI_PARTICIPANT_README.MD:75-156` — ambient param tables, default prompt blocks (`112,133,151`), choice-line section to `1. {choice_1}\n2. {choice_2}` and note quota-switched content per choice.
8.  **Tests & verification:** Add/adjust `src/tests/test_ai_agents.py` (or `test_ai_prompts` if exists) to assert rendered `pairwise_messages(...).content` contains `1. ` line followed immediately by `2. ` line, `choice_line` absent in defaults but tolerated via fallback. Manual `python3 -c` checks for single/factor/criteria with `allow_skip_tie=True/False`; run `pytest src/tests/test_ai_agents.py` (27 tests previously). Verify no toteboard/board file changes.

**Options and Trade-offs:**
*   **Backward compat:** (A) Dual-support with deprecation warning — `_safe_format` tries `choice_1/2`, falls back to `choice_line` split on `\n` — preserves custom env overrides, no break. (B) Hard break — require migration — simpler code but breaks deployed overrides. **Recommendation: (A) temporary dual-support + log once, remove next minor.**
*   **Prefix/style:** (A) Hard-coded `1. {choice_1}\n2. {choice_2}` (spec) — unambiguous, trivial LLM parsing (`parse_pairwise_choice` already handles `1`/`2`). (B) Configurable prefix/sep (`AI_PROMPT_CHOICE_PREFIX`, `AI_PROMPT_CHOICE_SEPARATOR`) — flexibility for i18n/ `1:` vs `1.` but adds config surface. **Recommendation: hard-code `1. \n2. ` now, extract to constants `_CHOICE_PREFIX_1="1. "` if needed later.**
*   **Source of `choice_1/2` values:** (A) Derive from existing two sentences by reusing same string for both lines (simplest: `choice_1 = choice_line`, `choice_2 = choice_line` or split sentence). (B) New env vars `AI_PROMPT_CHOICE_1_TIE_SKIP`/`AI_PROMPT_CHOICE_1_STRICT` and `AI_PROMPT_CHOICE_2_*` for precise per-choice wording (enables `1. Respond with 1 or TIE` vs `2. Respond with 2 or SKIP`). **Recommendation: (A) for fast-track, keep 2 existing env vars and map to both `choice_1/2` (`choice_1 = tie_skip_line; choice_2 = strict_line` is wrong — instead duplicate same selected line); note future split as follow-up if per-choice distinction needed.**
*   **>2 choices:** Hard-code 2-choice vs template loop `choice_N`. Keep 2-choice hard-coded; leave `choice_3` placeholder as future extension point without over-engineering.
[comment: plan completed 2026-08-21T22:13:27.454Z | via executor-opencode | entryId e-20260821-0002 | artifacts: ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-11-03-406Z-plan-2qdjty.request.md, ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-11-03-406Z-plan-2qdjty.response.md, ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-11-03-406Z-plan-2qdjty.trace.log, ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-11-03-406Z-plan-2qdjty.result.json]


## Build Summary
### agent
Migrating AI voting prompt to numbered choices — updating templates and rendering.Core prompt settings updated — now refining the runtime prompt assembly.Prompt logic migrated — now updating documentation.Verification passed — finalizing the release.Build summary — Prompting for AI agent voting

**Commit:** `43eda5a` — `feat(ai): migrate AI voting prompts to choice_1/choice_2 with numbered prefixes`

**Major touch points:**
- `src/config/config_settings.py:13` — `VERSION` bump `0.7.77` → `0.7.78`
- `src/config/config_settings.py:37-55` — placeholder comments updated from `{choice_line}` to `{choice_1} {choice_2}`; three template defaults (`AI_PROMPT_SINGLE_OPTION_TEMPLATE`, `AI_PROMPT_FACTOR_OPTION_TEMPLATE`, `AI_PROMPT_FACTOR_RANKING_TEMPLATE`) changed from `…\n\n{choice_line}` to `…\n\n1. {choice_1}\n2. {choice_2}`
- `src/utils/ai/prompts.py:82-108` — `_DEFAULT_SINGLE`, `_DEFAULT_FACTOR_OPTION`, `_DEFAULT_FACTOR_RANKING` mirrored to `1. {choice_1}\n2. {choice_2}`
- `src/utils/ai/prompts.py:110-145` — added `_DEPRECATED_CHOICE_LINE_WARNED`, `_sanitize_choice_line()` (strips newlines/whitespace to preserve `1.`/`2.` layout) and `_maybe_warn_legacy_choice_line()` (logs once via `utils_show` when `{choice_line}` detected)
- `src/utils/ai/prompts.py:148-185` — `pairwise_messages()` docstring updated to list `choice_1, choice_2` (legacy noted), computes `selected = tie_skip/strict`, `sanitized = _sanitize_choice_line(selected)`, `choice_1 = choice_2 = choice_line = sanitized` for dual support
- `src/utils/ai/prompts.py:200-215`, `223-245`, `260-275` — all three branches (criteria factor-ranking, factor-option, single) now build `params` with `choice_1`, `choice_2`, `choice_line`, call `_maybe_warn_legacy_choice_line(tpl)` before `_safe_format`/`tpl.format`, ensuring `1. {choice_1}\n2. {choice_2}` rendered on successive lines (single `\n`, no blank) and legacy `{choice_line}` auto-fallback
- `docs_examples/AI_PARTICIPANT_README.MD:75-96` — ambient param tables updated to `{choice_1} {choice_2}`, added deprecation note for `{choice_line}`
- `docs_examples/AI_PARTICIPANT_README.MD:98-160` — default prompt blocks changed to `1. {choice_1}\n2. {choice_2}` and choice-line description expanded to show per-choice duplicated rendering and migration note

**Verification:** `python -c` checks confirmed defaults contain `choice_1`/`choice_2` not `choice_line`, `pairwise_messages` for single/factor/criteria with `allow_skip_tie=True/False` emits final two lines `1. …` then `2. …` with correct quota-switched text, legacy `choice_line` template still renders via fallback with deprecation log; `pytest src/tests/test_ai_agents.py` — 27 passed.
[comment: build completed 2026-08-21T22:16:38.056Z | via executor-opencode | entryId e-20260821-0003 | artifacts: ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-13-27-499Z-build-0yuhqw.request.md, ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-13-27-499Z-build-0yuhqw.response.md, ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-13-27-499Z-build-0yuhqw.trace.log, ./prompting-for-ai-agent-voting-333pnm/2026-08-21T22-13-27-499Z-build-0yuhqw.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T22:16:38.056Z build completed (e-20260821-0003)
- 2026-08-21T22:13:27.454Z plan completed (e-20260821-0002)
- 2026-08-21T22:11:03.358Z expand completed (e-20260821-0001)
- 2026-08-21T22:10:36.547Z created (source: user)
