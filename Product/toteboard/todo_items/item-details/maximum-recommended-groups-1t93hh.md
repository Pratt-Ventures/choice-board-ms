# Maximum Recommended Groups

## Short Description
### user
We just changed the maximum to be the same as the minimum.

It states the hard max is the max plus 2. Let's change this on the user interface and in the actual comparison process to max + 1. A user can always continue up to one group above the max, not the prior 2.
[comment: updated 2026-08-19T17:03:20.060Z | id maximum-recommended-groups-1t93hh]

## Expanded Description
### agent
We recently set the recommended maximum group count equal to the minimum, but the hard ceiling is still recommended max + 2. Change the UI and the comparison process so a user may continue only one group above the recommended maximum (max + 1), not two. Keep the recommended max itself unchanged; only the overage allowance drops from two extra groups to one.

- Scope: UI copy, limits, and continue/stop controls plus the comparison-process check that currently allows max + 2.
- Treat max + 1 as the hard stop everywhere those paths enforce or describe the ceiling.
- Confirm min == max recommended does not make “one more group” copy or gating confusing.
- Audit other “plus 2” strings, validation, and stop conditions so they stay consistent.
- Open: should in-flight comparisons already at max + 2 be grandfathered or forced to stop?
- Open: must backend/API validation match the UI, or is the comparison-process change sufficient?
[comment: expanded description edited 2026-08-19T17:03:20.060Z]


## Plan
### agent
I'll research how recommended max and the +2 ceiling are enforced, then draft the plan.Graph exists — querying it and searching the codebase for the max+2 ceiling.Key sites found. Reading the clamp, UI continue controls, and tests next.Reading UI continue/stop copy and the session/API hard-max checks.# Maximum Recommended Groups — execution plan

Code uses **passes**, not groups: recommended max is `max_recommended_passes`; the hard ceiling is `hard_max_passes = recommended + 2`. A pass is a full round of comparison groups. Do not change questions-per-group or intra-pass group counts.

## Implementation steps

1. **Canonical overage** — In `hard_max_passes()` (`src/utils/sort_compare.py:355`), change `+ 2` to `+ 1`. Leave `clamp_max_recommended_passes` and min/max defaults unchanged.

2. **Stop duplicating the formula** — Replace hardcoded `"hard_max_passes": mx + 2` in `src/api/app_project_vote_events.py:185` and `src/api/app_shared_link_ext_access.py:208` with `hard_max_passes(mx, mn)` so settings payloads cannot drift from the comparison loop in `pick_next_sort_group` (`vote_sort_session.py:703`).

3. **Copy** — Update “hard limit is max + 2” / “Hard stop is this value + 2.” in:
   - `client/pages/projects/[id]/edit.vue:188`
   - `src/db/models/customer_projects.py:71`
   - `src/api/app_customer_project_management.py:91`  
   Soft-stop UI (`reachedMaxRecommended`, “Continue comparing”) already gates at recommended max and then follows `session_complete`; no new “two more” strings. Confirm min == max still reads as one optional extra pass.

4. **In-flight sessions** — Do not abort mid-group. `pick_next_sort_group` already resumes in-progress groups before the hard-max loop, then issues nothing past the new ceiling. Existing max+2 results stay in the DB. After deploy, a session already on pass max+2 can finish the open group, then stop.

5. **Tests** — `test_pass_clamps`: `hard_max_passes(4) == 6` → `== 5`. Add `hard_max_passes(2, 2) == 3` and `hard_max_passes(10) == 11`. Add a `pick_next_sort_group` case: after completing `max+1` passes, `group is None` and `session_complete`. Assert both settings payloads report the same `hard_max_passes` as the helper. Ignore Jacobsthal `b + 2 * a`, BT `pos + 2`, and bug-report MAX+2.

6. **Verify** — Run `src/tests/test_sort_compare.py` and the project/vote tests that read `hard_max_passes` / pass settings. Smoke: min == max == 2 → soft stop after pass 2, Continue starts pass 3, then hard stop (no second extra pass).

## Clarifying questions

1. Ticket says “groups”; the ceiling is **passes**. Confirm we change `hard_max_passes` only (one extra pass), not one extra group inside a pass.
2. Grandfather in-progress max+2 groups (finish current group, issue no new ones) — or force-stop immediately, including mid-group?
3. Must settings/API `hard_max_passes` match the process (recommended), or is changing `hard_max_passes()` alone enough?

## Options and recommendation

| Topic | Options | Recommendation |
|---|---|---|
| Overage | Keep `+ 2` vs `+ 1` | **`+ 1`** — requested; one shared helper. |
| API vs process | Process-only vs process + settings payloads | **Both, via `hard_max_passes()`** — otherwise the client is told +2 while issue/stop uses +1. No extra request-body pass-index validator; issue is the gate. |
| In-flight max+2 | Force-stop mid-group vs finish current group | **Finish current group, then stop** — already how resume works; no migration. |
| min == max copy | Special-case vs keep current soft-stop copy | **Keep current copy** — it never says “two more”; edit hint becomes “+ 1”. |
[comment: plan completed 2026-08-19T17:40:16.236Z | via executor-opencode | entryId e-20260819-0001 | artifacts: ./maximum-recommended-groups-1t93hh/2026-08-19T17-37-14-083Z-plan-oylshl.request.md, ./maximum-recommended-groups-1t93hh/2026-08-19T17-37-14-083Z-plan-oylshl.response.md, ./maximum-recommended-groups-1t93hh/2026-08-19T17-37-14-083Z-plan-oylshl.trace.log, ./maximum-recommended-groups-1t93hh/2026-08-19T17-37-14-083Z-plan-oylshl.result.json]


## Build Summary
### agent
I'll implement the hard-max change from +2 to +1 per the plan, starting with the canonical helper, settings payloads, and copy.Reading the files to update and existing tests.Implementing the canonical +1 overage, shared helper in settings payloads, copy, and tests.Running the sort-compare and related vote tests.Tests passed. Rebuilding the UI and regenerating OpenAPI snapshots.Regenerating OpenAPI snapshots for the updated field descriptions.Staging only the implementation files and committing.Hard stop is now recommended max + 1. In-flight sessions can finish the open group; no new pass is issued past the new ceiling.

**Touch points**
- `src/utils/sort_compare.py:356` — `hard_max_passes()` is `clamped + 1`
- `src/api/app_project_vote_events.py:186` / `src/api/app_shared_link_ext_access.py:209` — settings use `hard_max_passes(mx, mn)`
- `src/utils/vote_sort_session.py:703` — issue/stop already follows that helper
- Copy: `client/pages/projects/[id]/edit.vue:188`, `src/db/models/customer_projects.py:71`, `src/api/app_customer_project_management.py:91`
- Tests: `src/tests/test_sort_compare.py:313–315`, `:506`, `:525`, `:542`

**Verify:** 65 passed (`test_sort_compare`, `test_project_votes`, `test_manage_projects`). Static client rebuilt. OpenAPI snapshots updated.

**Commit:** `555e8b466543c1894047fef4ff21688ee50551dc`  
Allow only one comparison pass past the recommended maximum
[comment: build completed 2026-08-19T17:50:22.363Z | via executor-opencode | entryId e-20260819-0002 | artifacts: ./maximum-recommended-groups-1t93hh/2026-08-19T17-40-16-342Z-build-bc9oir.request.md, ./maximum-recommended-groups-1t93hh/2026-08-19T17-40-16-342Z-build-bc9oir.response.md, ./maximum-recommended-groups-1t93hh/2026-08-19T17-40-16-342Z-build-bc9oir.trace.log, ./maximum-recommended-groups-1t93hh/2026-08-19T17-40-16-342Z-build-bc9oir.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T17:50:22.363Z build completed (e-20260819-0002)
- 2026-08-19T17:40:16.236Z plan completed (e-20260819-0001)
- 2026-08-19T17:01:30.275Z expand completed (e-20260819-0005)
- 2026-08-19T16:50:10.435Z created (source: user)
