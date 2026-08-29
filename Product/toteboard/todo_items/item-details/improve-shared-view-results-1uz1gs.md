# Improve Shared View results

## Short Description
### user
On the shared viewer results page, we present a simple 'Thank You' witthe number of comparisons performed and a ranked list.

Change the ranked list to an attractive table, showing confidence and range settings like on the full dashboard (but just for the this user). If multiple factors were used, show the factors in the right side with a similar appropraite view.

This may involve updates the the share results and the UI.
[comment: created 2026-08-20T00:47:31.987Z | id improve-shared-view-results-1uz1gs]

## Expanded Description
### agent
I'll inspect the shared viewer results page and dashboard ranking UI so the expansion matches the current implementation.I'll read the existing todo item and the shared-results vs dashboard ranking UI next.The thank-you screen lives in `ShareVoteSession.vue`; I'll compare it with the dashboard ranking table next.The shared `vote_view` complete screen in `ShareVoteSession.vue` currently shows a Thank You, comparison count, and a plain numbered list from `submitter_summary.alternative_leaderboard`. Replace that list with a personal ranking table in the same visual language as the dashboard (`results.vue` overall ranking): rank, title, score, confidence, and range (rank CI / expected or mean rank), scoped only to this viewer. Keep the Thank You and count; when multiple factors were used, add a right-hand factor ranking using the same treatment. This may require enriching `build_personal_submitter_summary` / share complete and vote-view payloads (including project settings) so the UI has confidence, ranges, and `factor_leaderboard` instead of titles only.

- Scope: `vote_view` complete/results only (`ShareVoteSession` + share APIs); do not change group/report shares or expose other participants.
- Reuse `ranking.ts` / dashboard rank-row patterns rather than a one-off list; hide the factor pane when there is only one factor.
- Confirm `submitter_summary` actually includes per-option confidence, `rank_ci95` / expected rank, scores, and factor weights; pass project settings into the personal report if missing.
- Keep it this-user-only: no participant list, group metrics, or cross-voter agreement.
- Tests: share complete/vote-view payload shape and a UI assertion that the table (and factor pane when multi-factor) render.
- Open: table vs dashboard rank-rows; include insight chips or only per-row confidence/range; apply the same treatment to in-app `probe.vue` complete?
[comment: expand completed 2026-08-20T00:49:56.634Z | via executor-opencode | entryId e-20260820-0001 | artifacts: ./improve-shared-view-results-1uz1gs/2026-08-20T00-47-32-052Z-expand-0qm92i.request.md, ./improve-shared-view-results-1uz1gs/2026-08-20T00-47-32-052Z-expand-0qm92i.response.md, ./improve-shared-view-results-1uz1gs/2026-08-20T00-47-32-052Z-expand-0qm92i.trace.log, ./improve-shared-view-results-1uz1gs/2026-08-20T00-47-32-052Z-expand-0qm92i.result.json]


## Plan
### agent
I'll inspect the shared results page and dashboard ranking UI so the plan matches the current implementation.Graphify is available; I'll query it and read the share-results vs dashboard ranking code.I'll compare the dashboard rank table, share payload, and ranking helpers next.## Improve Shared View results

Current thank-you screen is `ShareVoteSession.vue` (`completeView`): title list from `submitter_summary.alternative_leaderboard`. Dashboard language lives in `results.vue` rank-rows + `client/utils/ranking.ts`. Personal payload is already richer than the UI uses.

### 1. Implementation steps

1. **Pass project settings into the personal report.**  
   `build_personal_submitter_summary` already accepts `settings` but share complete (`app_shared_link_ext_access.py` ~753 and ~830) and in-app mark-complete (`app_project_vote_events.py` ~548) omit it. Pass `ranking_settings_with_project_influence(...)` so `ranking_mode` / `top_n` match the project (needed for range + chance captions).

2. **Enrich `submitter_summary` (this-user only).**  
   Keep `alternative_leaderboard` / `factor_leaderboard` as the existing `option_ranking` / `factor_ranking` rows (they already have `score`, `rank_ci95`, `expected_rank`, `p_best` / `p_top_n`, factor `weight` / `weight_ci95` / `discrimination` / `leverage`). Add `ranking_mode`, `top_n`, and report-level `confidence` (and optionally `stability` / `multi_pass`). Do **not** attach `participants`, `dispersion`, or other voters. Do not change group/report share payloads.

3. **Replace the numbered list in `ShareVoteSession.vue`.**  
   Keep Thank You + comparison count. Map leaderboards with `mapServerRanking`. Render dashboard-style `.rank-row` cards (not a one-off `<ol>`): rank, title, score + bar, then caption via `formatRankCi` / `formatExpectedRank` / `optionChanceCaption` using `projectSettings.ranking_mode` (fallback `submitter_summary.ranking_mode`). Omit group-count, polarizing, insight chips, weighting selector, and participant lists.

4. **Multi-factor right pane.**  
   Two-column layout (`lg`: options 7 / factors 5). Show factor pane only when `factor_leaderboard.length > 1` (same rule as dashboard / share report). Reuse share-report factor treatment: importance, weight CI, differentiation, leverage. Single-factor: options only, full width.

5. **Tests.**  
   - Payload: extend `test_ext_vote_view_and_report_open_access` (or a focused complete-path test) so vote-view complete `submitter_summary` includes `score`, `rank_ci95` (or `expected_rank`), `ranking_mode`, and `factor_leaderboard`.  
   - Unit: `build_personal_submitter_summary` with settings → mode-aware fields; multi-factor includes factor rows with weights.  
   - UI: assert complete view renders `.rank-row` (and factor heading when ≥2 factors). Prefer a small ranking helper / payload mapping test in `ranking.test.ts` if a Vue mount test is not already in place; do not add a heavy e2e unless one already covers vote-view complete.

### 2. Clarifying questions

1. **Literal table vs rank-rows?** Brief says “table”; dashboard uses score-bar cards. Prefer cards (below).
2. **Per-row confidence?** Option rows have no `confidence`; dashboard puts confidence in insight chips and range/chance on each row. Show range + chance per row; optional one-line “Confidence: Solid” from report-level metric — not chips and not invented per-option scores.
3. **Apply the same complete screen to in-app `probe.vue`?** That page already links to full results. Default: **no**.
4. **Factor sort toggles** (Rank / Importance / Differentiation / Leverage) on the share thank-you? Default: **no** — ranked list only.

### 3. Options and trade-offs

| Option | Pros | Cons |
|---|---|---|
| **A. Dashboard rank-rows + right factor pane** | Same visual language; helpers already exist; attractive on mobile | Not a literal HTML table |
| **B. `v-data-table` columns (rank / title / score / confidence / range)** | Matches “table” wording | No score bars; “confidence” column is empty or fake; clashes with dashboard |
| **C. Extract a shared `RankRows` component used by results + share report + vote-view** | DRY | Extra refactor; out of FAST TRACK scope |

**Recommendation: A.** Copy the share-report rank-row markup into `ShareVoteSession` (narrower captions), feed it with `ranking.ts`, put factors on the right when multi-factor. Enrich the personal payload with settings/`ranking_mode` so ranges match the dashboard. Leave `probe.vue`, group/report shares, and component extraction alone.
[comment: plan completed 2026-08-20T00:52:56.254Z | via executor-opencode | entryId e-20260820-0002 | artifacts: ./improve-shared-view-results-1uz1gs/2026-08-20T00-49-56-713Z-plan-wx9btx.request.md, ./improve-shared-view-results-1uz1gs/2026-08-20T00-49-56-713Z-plan-wx9btx.response.md, ./improve-shared-view-results-1uz1gs/2026-08-20T00-49-56-713Z-plan-wx9btx.trace.log, ./improve-shared-view-results-1uz1gs/2026-08-20T00-49-56-713Z-plan-wx9btx.result.json]


## Build Summary
### agent
I'll inspect the shared results page, dashboard ranking UI, and personal submitter payload so the implementation matches the current design.Graphify is available — I'll query it and read the share-results, dashboard ranking, and payload builders in parallel.Next I’ll read the personal-summary builder, share complete endpoints, and dashboard rank-row markup.I have the payload and UI shape. Next I’ll pass project settings into the personal summary, enrich the complete payload, and replace the thank-you list with dashboard-style rank rows.I’ll move the helper below `mapServerRanking` so TypeScript can resolve its return type.Running the ranking unit tests and the share complete payload tests next.Tests passed. Rebuilding the published UI next.UI generate succeeded. Checking status and staging only the files for this work.## Build summary

Vote-view complete now keeps Thank You + comparison count, then shows dashboard-style rank-rows (score bar, rank CI / expected rank, chance caption) scoped to this viewer. Multi-factor adds a right-hand “What matters most” pane; a single factor stays full-width. Personal payload now includes `ranking_mode`, `top_n`, and report-level `confidence` (no participants / dispersion).

**Commit:** `764c01bba579ec59dd2cce67d6a4e93604aa003b`  
Improve shared vote-view complete results

### Touch points
- `src/utils/vote_ranking.py:912` — personal summary adds `ranking_mode` / `top_n` / `confidence`
- `src/api/app_shared_link_ext_access.py:753` / `:833` — pass project ranking settings on complete + vote-view reopen
- `src/api/app_project_vote_events.py:548` — same settings on in-app mark-complete
- `client/components/ShareVoteSession.vue:56` — thank-you rank-rows; `:98` factor pane
- `client/utils/ranking.ts:377` — `personalRankingsFromSummary`
- `src/tests/test_share_ext_access.py` — vote-view complete payload
- `src/tests/test_vote_ranking_probes.py:551` — unit: mode + factor weights
- `client/utils/ranking.test.ts:120` — mapping + single-factor hide

Verified: ranking unit tests 9/9; pytest personal summary + vote-view complete + mark-complete 4/4; `static_client` rebuilt. Version `0.7.57`.
[comment: build completed 2026-08-20T01:05:11.649Z | via executor-opencode | entryId e-20260820-0003 | artifacts: ./improve-shared-view-results-1uz1gs/2026-08-20T00-52-56-323Z-build-pz7jbg.request.md, ./improve-shared-view-results-1uz1gs/2026-08-20T00-52-56-323Z-build-pz7jbg.response.md, ./improve-shared-view-results-1uz1gs/2026-08-20T00-52-56-323Z-build-pz7jbg.trace.log, ./improve-shared-view-results-1uz1gs/2026-08-20T00-52-56-323Z-build-pz7jbg.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-20T01:05:11.649Z build completed (e-20260820-0003)
- 2026-08-20T00:52:56.254Z plan completed (e-20260820-0002)
- 2026-08-20T00:49:56.634Z expand completed (e-20260820-0001)
- 2026-08-20T00:47:31.987Z created (source: user)
