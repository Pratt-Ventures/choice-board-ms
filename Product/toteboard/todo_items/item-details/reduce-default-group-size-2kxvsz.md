# Reduce default group size

## Short Description
### user
When configuring a project, the default group size is pinned at the ford-johnson predicted full sort maximum. The groups often seem too large and confidence is reached before that point, especially in top-n situations.

Reduce the default group size to two-thirds (67%) of the ford johnson estimate, subject any contraints or minimums. The range will not be changed.

Keep the ranges the same,
[comment: created 2026-08-21T12:01:43.743Z | id reduce-default-group-size-2kxvsz]

## Expanded Description
### agent
When configuring a project, the default comparison group size is currently pinned to the Ford–Johnson predicted full-sort maximum, which often overshoots: confidence is typically reached earlier, especially for top-n. Change the default to two-thirds (67%) of that Ford–Johnson estimate, still applying existing constraints and minimums so the value cannot go invalid or below allowed floors. Do not change the configurable range (min/max); only the initial default should move. Existing projects and already-saved group sizes should be left as-is unless they currently inherit this default at configure time.

- Scope: default group-size initialization only (Ford–Johnson estimate × 0.67), then clamp with current min/constraints; leave min/max range UI and validation unchanged.
- Apply the 67% reduction before clamping so floors still win when the scaled value is too small.
- Confirm rounding (e.g. floor vs round) and that top-n vs full-sort share the same default rule.
- Do not retune Ford–Johnson itself, confidence logic, or persisted project settings.
- Open: should 67% apply only at first configure, or also when resetting defaults? Any tests/docs that assert the old full-sort maximum default?
[comment: expand completed 2026-08-21T12:10:50.896Z | via executor-opencode | entryId e-20260821-0003 | artifacts: ./reduce-default-group-size-2kxvsz/2026-08-21T12-10-19-283Z-expand-mipfwp.request.md, ./reduce-default-group-size-2kxvsz/2026-08-21T12-10-19-283Z-expand-mipfwp.response.md, ./reduce-default-group-size-2kxvsz/2026-08-21T12-10-19-283Z-expand-mipfwp.trace.log, ./reduce-default-group-size-2kxvsz/2026-08-21T12-10-19-283Z-expand-mipfwp.result.json]


## Plan
### agent
I'll locate how default group size is initialized from the Ford–Johnson estimate so the plan matches current constraints.Found the group-size helpers; next I’ll read initialization, clamping, and tests.I’ll check client defaults, configure-time init, and tests that pin the old FJ maximum.## Plan: reduce default group size to 67% of FJ

Default lives in one place on each side: `default_questions_per_group_for_n` (`src/utils/sort_compare.py:293`) and `defaultQuestionsPerGroupForN` (`client/utils/sortCompare.ts:97`). Both currently clamp **FJ(n)** itself. Range is `question_budget_bounds` / `questionBudgetBounds`: `[ceil(FJ/2), FJ×2]` capped at unique pairs — leave those unchanged. Top-n vs full-sort already share this helper (no ranking-mode branch). Configure, Reset, item add/remove, and vote budgets all go through it when `*_explicit` is false.

### 1. Implementation steps

1. **Scale then clamp (Python + TS, keep in lockstep)**  
   For `n >= 2`: `scaled = round(FJ(n) * 2/3)`, then `clamp_questions_per_group(scaled, n)` / `clampQuestionsPerGroup(...)`. Apply 67% *before* clamp so the existing floor wins when scaled is too small (e.g. n=2: 0.67→1 after clamp). Leave `n < 2` fallback (`COMPARE_DEFAULT_QUESTIONS_PER_GROUP` / `DEFAULT_QUESTIONS_PER_GROUP = 20`) alone. Use `2/3` (not `0.67`) and the same rounding in both languages (`Math.round` / equivalent half-up) so Python and TS never drift.

2. **Do not touch range, FJ, confidence, or explicit saves**  
   No changes to `ford_johnson_budget`, `question_budget_bounds`, clamp helpers, ranking confidence, pair scheduler, or `*_explicit == true` paths. Slider/input `:min`/`:max` stay on bounds. Hint can still show the full FJ **estimate**; only the prefilled value moves.

3. **Inherit via the existing default helper (no migration)**  
   Non-explicit projects already recompute from this helper at configure, Reset, item sync (`sync_project_group_sizes`), and vote (`resolved_question_budgets`). Changing the helper is enough. Explicit/custom sizes stay. Do not rewrite stored rows.

4. **Update tests that pin default = FJ(n)**  
   - `src/tests/test_sort_compare.py`: `default_questions_per_group_for_n(5/8)`, `resolve_questions_per_group(..., explicit=False)`, `test_vote_session_uses_fj_default_until_group_size_explicit` (incl. `question_budget == ford_johnson_budget(12)`). n=12 FJ=30 → default 20; `option_batch_count(12, opt_default) == 1` may fail if 20 no longer covers 12 — assert against the new default, do not retune batching.  
   - `src/tests/test_manage_project_content.py`: retarget-on-add/remove/reset asserts `== ford_johnson_budget(n)` → `== default_questions_per_group_for_n(n)`.  
   Keep bounds tests (`lo == 4, hi == 10` for n=5) unchanged.

5. **Optional copy**  
   Advanced-tab copy says “Using the Ford–Johnson default” while the number will no longer equal the estimate. One-line tweak that default is ~two-thirds of the estimate; range text stays.

6. **Verify**  
   Run the sort-compare / project-content / project-votes tests above. Spot-check n=2 (floor), n=5 (7→5), n=8 (16→11), explicit override still clamped to the old range.

### 2. Clarifying questions

1. Rounding: nearest (`round` / `Math.round`) vs floor? Floor pins n=2–5 to the **minimum** of the range.
2. Should existing **non-explicit** live vote sessions pick up 67% immediately (current helper behavior), or only newly configured/reset projects?
3. Keep one default for top-n and full-sort (current code), or special-case top-n smaller?

### 3. Options and recommendation

| | Approach | Trade-off |
|---|---|---|
| A | Change the two default helpers only (67% then clamp) | Smallest diff; Reset, retarget, and votes all follow. Existing non-explicit projects inherit immediately. |
| B | 67% only at first configure; Reset/votes keep FJ(n) | Matches a strict reading of “first configure,” but splits “default” into two meanings and fights the explicit-flag design. |
| C | Floor instead of round | More reduction; for small n the default *is* the range min, so the slider looks stuck at the bottom. |
| D | Different default for top-n vs full-sort | Matches the “especially top-n” motivation; extra UI/API surface, out of stated scope. |

**Recommend A + round(2/3 × FJ) then clamp + same rule for top-n and full-sort + Reset uses the new default.** Non-explicit means “follow current default”; explicit rows are the leave-as-is path. Floor only as a follow-up if groups still feel large.
[comment: plan completed 2026-08-21T12:12:42.294Z | via executor-opencode | entryId e-20260821-0004 | artifacts: ./reduce-default-group-size-2kxvsz/2026-08-21T12-10-50-972Z-plan-l6ax8z.request.md, ./reduce-default-group-size-2kxvsz/2026-08-21T12-10-50-972Z-plan-l6ax8z.response.md, ./reduce-default-group-size-2kxvsz/2026-08-21T12-10-50-972Z-plan-l6ax8z.trace.log, ./reduce-default-group-size-2kxvsz/2026-08-21T12-10-50-972Z-plan-l6ax8z.result.json]


## Build Summary
### agent
I'll locate the default group-size helpers and apply the 67% scale-then-clamp change in lockstep.I'll read the tests, UI copy, version, and changelog next so the default change stays in lockstep.Applying the 67% scale-then-clamp in both helpers, then updating tests and copy.The vote-session test failed on group budget; I'll trace how that value is assigned.The issued group is a shuffled batch, so I'll assert the budget against that batch size.**Build summary** — default group size is now round(FJ(n)×2/3) then clamp. Range, FJ, confidence, and explicit saves unchanged. Top-n and full-sort share the helper. Version `0.7.67`. Static client rebuilt. 55 tests passed. No CHANGELOG.md.

**Touch points**
- `src/utils/sort_compare.py:293-298` — `default_questions_per_group_for_n`
- `client/utils/sortCompare.ts:97-100` — `defaultQuestionsPerGroupForN`
- `client/pages/projects/[id]/edit.vue:973` and `:980` — hint copy
- `src/tests/test_sort_compare.py:298-306`, `:413-437`
- `src/tests/test_manage_project_content.py:312`, `:333`, `:373`, `:384`

**Commit** `894438a` — Reduce default group size to two-thirds of the Ford-Johnson estimate
[comment: build completed 2026-08-21T12:19:33.605Z | via executor-opencode | entryId e-20260821-0005 | artifacts: ./reduce-default-group-size-2kxvsz/2026-08-21T12-12-42-367Z-build-n2uy0i.request.md, ./reduce-default-group-size-2kxvsz/2026-08-21T12-12-42-367Z-build-n2uy0i.response.md, ./reduce-default-group-size-2kxvsz/2026-08-21T12-12-42-367Z-build-n2uy0i.trace.log, ./reduce-default-group-size-2kxvsz/2026-08-21T12-12-42-367Z-build-n2uy0i.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T12:19:33.605Z build completed (e-20260821-0005)
- 2026-08-21T12:12:42.294Z plan completed (e-20260821-0004)
- 2026-08-21T12:10:50.896Z expand completed (e-20260821-0003)
- 2026-08-21T12:01:43.743Z created (source: user)
