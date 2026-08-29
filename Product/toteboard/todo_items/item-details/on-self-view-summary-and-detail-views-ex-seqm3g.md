# On self view summary and detail views expected range information

## Short Description
### user
Presently, the expected range of rank outcomes is shown like 'expected 2-4' or similar. A small horizontal bar with rank positions overlayed and then an area of increasing color gradient near the center of the predicted outcome, fading to the background color at the +/- 2 sd mark would be better. On hover over, it says 'visually shows the likely rank range of this item'  

This may take changes in data from the server to provide reasonable inputs for the gradations points. 5-7 shades seems sufficient.
[comment: created 2026-08-21T03:07:53.016Z | id on-self-view-summary-and-detail-views-ex-seqm3g]

## Expanded Description
### agent
Replace the textual expected-rank range (e.g. “expected 2–4”) on self-view summary and detail with a compact horizontal rank bar: tick marks for rank positions, a color gradient peaking at the predicted outcome and fading to the background at ±2 SD. Hover copy should read “visually shows the likely rank range of this item.” Server payloads may need extra fields so 5–7 gradient stops can be placed from mean and SD rather than inferred from a min–max string.

- Scope: self-view summary and detail only; keep existing range text as fallback or a11y if the viz cannot render.
- Data: confirm API currently exposes mean/SD (or equivalent) vs. only a discrete range; add 5–7 stop values or mean + SD if missing.
- Visual: map ranks on a linear axis; gradient intensity at the mode/mean, transparent at ±2 SD; overlay rank ticks without crowding small bars.
- Interaction: tooltip/title as specified; keyboard/screen-reader still need a numeric range.
- Open: exact color tokens vs. background, whether ±2 SD clips at rank 1/N, and whether summary uses a thinner bar than detail.
[comment: expand completed 2026-08-21T03:26:54.823Z | via executor-opencode | entryId e-20260821-0004 | artifacts: ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T03-26-13-965Z-expand-bee1qe.request.md, ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T03-26-13-965Z-expand-bee1qe.response.md, ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T03-26-13-965Z-expand-bee1qe.trace.log, ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T03-26-13-965Z-expand-bee1qe.result.json]


## Plan
### agent
I'll inspect the self-view rank-range UI and related API fields so the plan matches current code.Checking whether a knowledge graph exists, then locating the expected-rank UI and API fields.Self-view is the post-comparison ranking plus the share report. Next I’ll check payloads, CSS tokens, and whether mean/SD already exist.## Plan: self-view expected-rank range bar

**Current state.** Self-view ranking is `ShareVoteSession.vue` after mark-complete (`vote` / `vote_view`). Caption uses `formatRankCi(rank_ci95)` (`ranks 2–4`) plus, in `rank_all`, `expected {n}`. Payload already has 1-based `expected_rank` (posterior mean) and `rank_ci95` (2.5/97.5% quantiles). There is **no** posterior `rank_sd`. `participant_rank_sd` is across people — wrong input. Owner `results.vue` and share `report` are out of scope. No separate self-view “detail” page exists today.

---

### 1. Implementation steps

1. **Add posterior `rank_sd` in `rank_summary`** (`src/utils/bt_inference/ranks.py`): `float(ri.std())` next to `expected_rank`. Do not send 5–7 stop arrays from the server.

2. **Plumb it through ranking rows** in `_entries_from_fit` (and factor overlay in `_apply_factor_leverage`) so `submitter_summary.alternative_leaderboard` includes `rank_sd`. No migration.

3. **Backend tests:** `test_bt_inference.py` / `test_vote_ranking_probes.py` — `rank_sd` present, ≥ 0, and consistent with samples (near-certain item small SD; ties larger).

4. **Client mapping:** `mapServerRanking` + `personalRankingsFromSummary` forward `rank_sd`. Fallback if missing: `sd ≈ (ci_hi − ci_lo) / 3.92` from `rank_ci95`. If neither mean nor CI exists, no bar.

5. **Pure helper** `client/utils/rankRangeBar.ts` (unit-tested):
   - Axis: ranks `1…N` (N = list length).
   - Peak at `expected_rank`; fade to 0 at `mean ± 2·sd`.
   - **Clip** the painted band to `[1, N]`.
   - 7 CSS stops (mean, ±⅔ sd, ±4/3 sd, ±2 sd) via `color-mix` / `rgba(var(--pc-primary-rgb), α)` so light/dark `.rank-row` (`--pc-surface`) is the fade target.
   - Tick positions; if `N > 8`, ticks only, labels at `1` and `N`.

6. **Component `RankRangeBar.vue`:** compact horizontal track, overlay ticks, `v-tooltip` + `title` = `visually shows the likely rank range of this item`. `aria-hidden` on the graphic; **sr-only** numeric range (`formatRankCi` / expected). `density: compact | comfortable` (heights ~10px / ~16px). If viz cannot render, show existing caption text.

7. **Wire only self-view option rows** in `ShareVoteSession.vue` (replace visible `ranks …` / `expected …`; keep chance + polarizing copy). Score `v-progress-linear` stays. Do not change `results.vue` or `share/report`.

8. **Tests:** `ranking.test.ts` + new helper tests (stops, clip, CI fallback, mapper). Pytest for `rank_sd`. No new lint toolchain (none in repo).

---

### 2. Clarifying questions

1. **Surfaces:** Confirm **only** the post-complete “Your ranking” list (`ShareVoteSession`), not owner Results or the shared full report?
2. **“Detail”:** There is no second self-view density today. Ship compact on the list only, or also a comfortable bar (e.g. expanded row / later detail)?
3. **Peak:** Mean (`expected_rank`) vs median vs mode? Mean matches current “expected” copy.
4. **Visible numbers:** Hide `ranks 2–4` (sr-only only) or keep a short caption beside the bar?
5. **`vote` vs `vote_view`:** Same thank-you template — apply to both, or `vote_view` only?

---

### 3. Options and trade-offs

| | Approach | Trade-off |
|---|---|---|
| **A (rec.)** | Server `rank_sd` + client 7-stop CSS gradient | Tiny payload, theme-safe, matches the brief. Gaussian is an approximation of discrete ranks, especially near 1/`N`. |
| B | Server sends 5–7 stop values | Couples API to paint; any color/density tweak is a backend change. |
| C | Full `rank_pmf[1..N]` histogram | Most faithful; larger payload and a different viz than specified. Revisit if Gaussian looks wrong on small `N`. |
| D | Infer SD from `rank_ci95` only | No API change, but CI ≠ ±2 SD under skew, and peak can sit off-center. Use only as fallback. |

**Recommend A**, with D as fallback for old payloads. Clip ±2 SD at rank 1/`N`. Color: `--pc-primary` fading to transparent on `--pc-surface`. Default density compact on the list; add comfortable only if a detail surface is confirmed.

**Open (defaults if unanswered):** clip yes; mean peak; hide range text visually (keep a11y); both `vote` and `vote_view` thank-you lists; compact only until a detail view exists.
[comment: plan completed 2026-08-21T11:55:22.510Z | via executor-opencode | entryId e-20260821-0003 | artifacts: ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T11-52-12-616Z-plan-gr8xcq.request.md, ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T11-52-12-616Z-plan-gr8xcq.response.md, ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T11-52-12-616Z-plan-gr8xcq.trace.log, ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T11-52-12-616Z-plan-gr8xcq.result.json]


## Build Summary
### agent
Backend first — `rank_sd` in the posterior rank summary:Now plumb it through `_entries_from_fit` and `_apply_factor_leverage`:Backend tests next. Let me view the rest of the relevant test file:Backend green. Now the client pieces — helper first:Now the component:Now forward `rank_sd` in `mapServerRanking`:Now wire it into `ShareVoteSession.vue` (self-view option rows), keeping the old text as fallback:Now client tests. First verify how existing tests run with node 24:Test bugs (my assertions were wrong, not the helper): the renderable-input case was wrongly expected to be `null`, and the clipped case legitimately peaks at the clipped edge. Fixing the tests:The helper's local `finite` treats `null` as 0 (`Number(null) === 0`). Fixing:Client unit tests green. Verify backend suites still pass including share surface, then rebuild the UI:UI published. Run the share access-mode e2e suite to exercise the self-view flow end-to-end:Found it — the local `.env` has `LOGIN_2FA_MODE=admins`, and the e2e helper logs in as a customer admin, so the login gets a 2FA challenge with a cleared cookie; unrelated to this change. Process env overrides `.env`, so I can run the suite with 2FA disabled without touching any file:
[comment: build completed 2026-08-21T16:03:55.701Z | via executor-opencode | entryId e-20260821-0002 | artifacts: ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T15-12-10-106Z-build-ys8u7a.request.md, ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T15-12-10-106Z-build-ys8u7a.response.md, ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T15-12-10-106Z-build-ys8u7a.trace.log, ./on-self-view-summary-and-detail-views-ex-seqm3g/2026-08-21T15-12-10-106Z-build-ys8u7a.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T16:03:55.701Z build completed (e-20260821-0002)
- 2026-08-21T11:55:22.511Z plan completed (e-20260821-0003)
- 2026-08-21T03:26:54.823Z expand completed (e-20260821-0004)
- 2026-08-21T03:07:53.016Z created (source: user)
