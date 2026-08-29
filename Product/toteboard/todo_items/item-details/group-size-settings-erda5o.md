# Group size settings

## Short Description
### user
The group size settings should remember whether they had defaults changed. When new items are added, it should adjust to the FJ defaults unless they were explicitly set.
[comment: created 2026-08-19T16:37:04.644Z | id group-size-settings-erda5o]

## Expanded Description
### agent
I'll look up how group size settings and FJ defaults work so the expansion matches the codebase.Checking how group size and FJ defaults are stored so the expansion is accurate.Group size (`option_questions_per_group` / `factor_questions_per_group`) must track whether the user overrode the Ford–Johnson default, not just store a number. Today those fields are always persisted as ints and reclamped, so adding items cannot tell “still on default” from “user chose this budget.” If the value was never explicitly set, new items should retarget the current FJ default for the new `n`; if it was set, keep the user’s value (still clamp to `question_budget_bounds`).

- Scope: persist an explicit/default flag (or nullable until first edit) for option and factor group size; on item add/remove, apply FJ default only when not explicit.
- Recompute using `default_questions_per_group` / `ford_johnson_budget(n)` and existing clamp helpers; do not rewrite explicit values except to stay in bounds.
- Cover create/update APIs, vote session partitioning, and the project settings UI so the control can show default vs custom.
- Consider: treat matching the current FJ number as still-default, or only as default until the user touches the control?
- Open: should item deletion also retarget defaults? Independent flags per option vs factor? Migration for existing projects that already have stored ints?
[comment: expand completed 2026-08-19T16:38:16.259Z | via executor-opencode | entryId e-20260819-0001 | artifacts: ./group-size-settings-erda5o/2026-08-19T16-37-04-767Z-expand-amh3w6.request.md, ./group-size-settings-erda5o/2026-08-19T16-37-04-767Z-expand-amh3w6.response.md, ./group-size-settings-erda5o/2026-08-19T16-37-04-767Z-expand-amh3w6.trace.log, ./group-size-settings-erda5o/2026-08-19T16-37-04-767Z-expand-amh3w6.result.json]


## Plan

## Build Summary
### agent
I'll start by locating how group size and FJ defaults are stored so the flags and retargeting match existing code.Graphify is for Q&A, not this build. I'll read the project model, clamp helpers, and settings UI next.Next I’ll trace item add/remove, the settings UI, and how group-size is persisted so the flags stay consistent.I have the design: persist independent explicit flags, retarget FJ defaults on item add/remove, and keep user values only when they were set.Sync's extra commit was expiring the just-created item. I'll stop that expire so callers can still read `id`.**Group size settings remember default vs custom.** Option and factor budgets follow FJ(`n`) until the user sets them; item add/remove retargets only non-explicit values (still clamped). Independent flags; existing `20` / reclamped-default / FJ(`n`) rows stay non-explicit.

**Commit:** `4945fb4` — Remember whether group size left the Ford-Johnson default

**Touch points:** `src/db/models/customer_projects.py:87` flags · `src/alembic/versions/r9s0t1u2v3w4_group_size_explicit_flags.py:51` migration · `src/utils/sort_compare.py:293` / `:300` resolve · `src/utils/project_group_size.py:41` retarget · `src/db/models/customer_project_alternatives_criteria.py:372` add/remove hooks · `src/api/app_customer_project_management.py:128` create/update · `src/utils/vote_sort_session.py:163` / `:698` partitioning · `client/pages/projects/[id]/edit.vue:235` Default/Reset UI
[comment: build completed 2026-08-19T16:59:13.452Z | via executor-opencode | entryId e-20260819-0002 | artifacts: ./group-size-settings-erda5o/2026-08-19T16-38-16-308Z-build-fos5p4.request.md, ./group-size-settings-erda5o/2026-08-19T16-38-16-308Z-build-fos5p4.response.md, ./group-size-settings-erda5o/2026-08-19T16-38-16-308Z-build-fos5p4.trace.log, ./group-size-settings-erda5o/2026-08-19T16-38-16-308Z-build-fos5p4.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T16:59:13.452Z build completed (e-20260819-0002)
- 2026-08-19T16:38:16.259Z expand completed (e-20260819-0001)
- 2026-08-19T16:37:04.644Z created (source: user)
