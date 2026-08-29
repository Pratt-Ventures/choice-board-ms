# Maximum recommended passes on a project

## Short Description
### user
This appears to default to either 3 or 1 over the minimum and allows the lower value to be saved, even below the minimum.

Always make the minimum value in the up/down the on page min expected passes. When saving, ensure it is similarly enforced.

Change the default to the min number of passes. Project creators can increase if desired.
[comment: created 2026-08-19T16:41:12.552Z | id maximum-recommended-passes-on-a-project-1bg47x]

## Expanded Description
### agent
The maximum-recommended-passes field on a project currently defaults to either a hardcoded 3 or one above the page’s minimum expected passes, and the spinner/save path can persist a value below that on-page minimum. The control’s lower bound should always be the page’s min expected passes, and save should reject or clamp anything below that. Default the field to the minimum expected pass count so creators start at the floor and can raise it if they want.

- Scope: spinner min, default value, and save validation for max recommended passes on create/edit.
- Tie the up/down floor to the same on-page min expected passes used elsewhere.
- Enforce the same floor on save (clamp or reject); do not allow under-min persistence.
- Default new/unsaved values to min expected passes, not min+1 or 3.
- Confirm whether existing below-min records should be migrated, clamped on load, or left until next save.
- Keep UI and API/schema constraints consistent across create and edit.
[comment: expand completed 2026-08-19T16:59:56.938Z | via executor-opencode | entryId e-20260819-0003 | artifacts: ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T16-59-13-523Z-expand-v1ce3r.request.md, ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T16-59-13-523Z-expand-v1ce3r.response.md, ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T16-59-13-523Z-expand-v1ce3r.trace.log, ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T16-59-13-523Z-expand-v1ce3r.result.json]


## Plan
### agent
I'll inspect how max recommended passes is defaulted, bounded, and saved so the plan matches the current create/edit path.Key files are identified; next I’ll read the clamp helpers, create/edit form, and schema so the plan matches the real floor/default.## Maximum recommended passes — execution plan

**Current state:** Create/edit lives in `client/pages/projects/[id]/edit.vue`. Spinner `min` is hardcoded `3`; new-form default is `4` (`min_expected_passes` defaults to `2`). Load/save use `Math.max(3, …)` and ignore the on-page min, so min=5 / max=3 can be shown and posted. API `clamp_max_recommended_passes` (`src/utils/sort_compare.py`) already raises max to min on create/update, but still uses absolute floor `3` and default `4`. Vote/read paths already re-clamp.

### Implementation steps

1. **Shared clamp** — In `clamp_max_recommended_passes`, drop the hardcoded `3`/`4`. Floor = `clamp_min_expected_passes(min_passes)` (1–5, default 2). If value is omitted/invalid, default to that floor (not 4). Cap remains 10. `hard_max_passes` stays `clamped + 2`.
2. **Schema/defaults** — Set `max_recommended_passes` default to `2` (same as min) on `CustomerProject`, `CustomerProjectForm`, and `app_shared_link_ext_access`. Update copy from “3–10” to “≥ min expected, ≤ 10; hard stop is max+2”. No Alembic data migration.
3. **Create/edit UI** — Bind max spinner `:min` to the current on-page `min_expected_passes`. New/unsaved form: `max_recommended_passes = min_expected_passes` (2). On load, keep stored max if `>= min`, else clamp up. On save (create + update), send `Math.max(min, Math.min(10, n))` — never persist below min. Watch min: if it rises above max, bump max; if it falls, leave max.
4. **API already clamps** — Keep create/update calling `clamp_max_recommended_passes(mx, mn)`. After step 1 this also allows max=1 or 2 when min is 1 or 2.
5. **Tests** — Extend `test_pass_clamps`: `clamp_max_recommended_passes(None, 2)==2`, `(1, 1)==1`, `(2, 5)==5`, `(11, 2)==10`. Add create/update cases: max `<` min is clamped; omitted max defaults to min; max `==` min is stored. Existing `test_project_pass_settings_on_create` (3/5) stays valid. E2E helper `min=1, max=3` stays valid.
6. **Verify** — `test_sort_compare`, `test_project_votes`, `test_manage_projects`; lint/typecheck. OpenAPI regen only if that is the usual follow-up (hand-edit not required).

### Clarifying questions

1. Existing rows with max `<` min (unlikely if API clamp always ran): migrate, clamp on load only, or leave until next save?
2. When the user raises min above current max in the spinner, auto-bump max (recommended) or block the min change?
3. Should omitted API `max_recommended_passes` become min (2), or keep historical 4 for back-compat clients?

### Options and recommendation

| Topic | Options | Recommendation |
|---|---|---|
| Under-min save | Clamp vs 400/reject | **Clamp** — matches existing `clamp_*` style; UI should not offer illegal values anyway |
| Absolute floor of 3 | Keep `max(3, min)` vs floor = on-page min | **Floor = min** — required so default can be min when min is 1–2; hard stop is still +2 |
| Legacy rows | SQL migration vs clamp on read/save | **No migration** — vote/summary already clamp; edit load + next save fix the rest |
| Raising min | Auto-bump max vs reject | **Auto-bump** — keeps invariant without extra error UX |

Do not change vote/progress behavior beyond the clamp default/floor. Stored values that are already `>=` min stay as-is.
[comment: plan completed 2026-08-19T17:04:34.965Z | via executor-opencode | entryId e-20260819-0006 | artifacts: ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T17-01-30-315Z-plan-mkdhqn.request.md, ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T17-01-30-315Z-plan-mkdhqn.response.md, ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T17-01-30-315Z-plan-mkdhqn.trace.log, ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T17-01-30-315Z-plan-mkdhqn.result.json]


## Build Summary
### agent
I'll inspect the clamp helpers, create/edit form, and schema so the implementation matches the current floor and default.Reading the clamp helper, models, form, and tests next.Implementing clamp, schema defaults, UI floor/default, and tests.Running the targeted test suites and rebuilding the published UI.Tests need `PYTHONPATH` at the repo root so settings load. Retrying with that.Retrying tests from the repo root so `.env` loads correctly.Tests passed. Regenerating the sessions OpenAPI snapshot because form field defaults and descriptions changed.OpenAPI change is the expected default/description update. Committing only the related source files.**Build complete.** Max recommended passes now defaults to min expected passes; spinner and save both use that floor.

**Commit:** `bec1a01` — Floor maximum recommended passes at min expected passes

**Touch points**
- `src/utils/sort_compare.py:346-352` — clamp floor = min expected (1–5); omitted/invalid defaults to that floor, cap 10
- `src/db/models/customer_projects.py:69-71` — model default 2; copy “≥ min expected, ≤ 10”
- `src/api/app_customer_project_management.py:89-91` — form default/description match
- `src/api/app_shared_link_ext_access.py:84` — share payload default 2
- `client/utils/sortCompare.ts:72-83` — matching client clamps
- `client/pages/projects/[id]/edit.vue:174-181` spinner `:min`; `:639` new-form default 2; `:704-709` auto-bump max when min rises; `:1040-1044` load clamp; `:1263-1267` / `:1294-1298` save clamp
- `src/tests/test_sort_compare.py:305-313` — clamp cases
- `src/tests/test_project_votes.py:316` — create/update: omit→min, max==min stored, max&lt;min clamped
- `src/config/config_settings.py:17` — VERSION 0.7.53
- `openapi_sessions.json` — sessions schema default/description

**Verify:** 62 passed (`test_sort_compare`, `test_project_votes`, `test_manage_projects`). Static client rebuilt. No data migration; existing below-min rows clamp on load/next save.
[comment: build completed 2026-08-19T17:18:00.971Z | via executor-opencode | entryId e-20260819-0008 | artifacts: ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T17-04-35-039Z-build-20hmmm.request.md, ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T17-04-35-039Z-build-20hmmm.response.md, ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T17-04-35-039Z-build-20hmmm.trace.log, ./maximum-recommended-passes-on-a-project-1bg47x/2026-08-19T17-04-35-039Z-build-20hmmm.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T17:18:00.972Z build completed (e-20260819-0008)
- 2026-08-19T17:04:34.965Z plan completed (e-20260819-0006)
- 2026-08-19T16:59:56.938Z expand completed (e-20260819-0003)
- 2026-08-19T16:41:12.552Z created (source: user)
