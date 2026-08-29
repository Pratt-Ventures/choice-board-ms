# Ranking Table clarification

## Short Description
### user
On the 'Your Ranking' after individual contribution via a share (with view enabled), on a line below "Your ranking" header, add, in small text, "Decision factors contribute according to importance ranked factors; Rank percentage is first vs last likelihood."

On the Overall Ranking  table for project results, add "Rank percentage is first vs last likelihod." to the criteria summary presented based on sort mode.
[comment: created 2026-08-20T01:22:39.378Z | id ranking-table-clarification-1k0dqx]

## Expanded Description
### agent
Add a short helper line under the contributor “Your ranking” header (share link with view enabled) stating that decision factors contribute by importance-ranked weight and that rank percentage is first vs last likelihood. On the project Overall Ranking table, append the same rank-percentage sentence to the existing sort-mode criteria summary. Copy stays secondary so it explains scoring without changing layout, math, or other result views.

- Scope: Your Ranking subtitle plus Overall Ranking criteria summary only.
- Do not change ranking calculations, columns, sort modes, or other pages.
- Match existing small/helper typography and criteria-summary placement.
- Confirm exact strings and whether to fix the brief’s “likelihod” typo.
- Confirm this is only the share+view-enabled Your Ranking surface.
- Confirm Overall Ranking text is appended for every sort mode, not one mode.
[comment: expand completed 2026-08-20T01:23:21.186Z | via executor-opencode | entryId e-20260820-0001 | artifacts: ./ranking-table-clarification-1k0dqx/2026-08-20T01-22-39-418Z-expand-oujqji.request.md, ./ranking-table-clarification-1k0dqx/2026-08-20T01-22-39-418Z-expand-oujqji.response.md, ./ranking-table-clarification-1k0dqx/2026-08-20T01-22-39-418Z-expand-oujqji.trace.log, ./ranking-table-clarification-1k0dqx/2026-08-20T01-22-39-418Z-expand-oujqji.result.json]


## Plan

## Build Summary
### agent
I'll locate the Your Ranking and Overall Ranking UI surfaces first, then add the helper copy without changing ranking math or layout.Found the share ranking header. Next I’ll locate the Overall Ranking criteria summary and existing helper typography.Confirming copy on the share Your Ranking header and the project Overall Ranking sort-mode summary. Checking version, changelog, and tests next.Copy targets are confirmed. I'll add the helper lines and check commit style plus any tests that assert this text.Implementing the helper copy on both surfaces, then bumping the version and publishing the UI.Rebuilding the published UI so FastAPI serves the new helper copy.Build succeeded. Staging only the ranking-copy and version files, then committing.Worktree looks cleaner than expected. Checking whether the edits persisted or were already committed.**Ranking Table clarification** — helper copy only; scoring/layout unchanged. Typo fixed to “likelihood”. Your Ranking subtitle is only on the share complete surface (`ShareVoteSession`). Rank-percentage sentence appended for every Overall Ranking sort mode.

**Touch points**
- `client/components/ShareVoteSession.vue:69-72` — caption under “Your ranking”
- `client/pages/projects/[id]/results.vue:81` — criteria summary
- `client/pages/projects/[id]/results.vue:622-627` — `resultViewExplanation` (equal / adjusted / selected factor)
- `src/config/config_settings.py:17` — `0.7.58`

Nothing to commit: source already in `044aa26` (`readme.md / agents.md update and toteboard status.`). Static client rebuilt.
[comment: build completed 2026-08-20T01:28:57.497Z | via executor-opencode | entryId e-20260820-0002 | artifacts: ./ranking-table-clarification-1k0dqx/2026-08-20T01-23-21-357Z-build-wb6zfs.request.md, ./ranking-table-clarification-1k0dqx/2026-08-20T01-23-21-357Z-build-wb6zfs.response.md, ./ranking-table-clarification-1k0dqx/2026-08-20T01-23-21-357Z-build-wb6zfs.trace.log, ./ranking-table-clarification-1k0dqx/2026-08-20T01-23-21-357Z-build-wb6zfs.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-20T01:28:57.497Z build completed (e-20260820-0002)
- 2026-08-20T01:23:21.186Z expand completed (e-20260820-0001)
- 2026-08-20T01:22:39.378Z created (source: user)
