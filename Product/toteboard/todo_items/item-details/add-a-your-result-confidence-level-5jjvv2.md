# Add a 'Your Result Confidence Level'

## Short Description
### user
During comparison process, show a 'Current Ranking Confidence Achieved' bar. This will be a progress bar that goes from 'None' to 'Low' to 'Moderate' to 'Fair' to 'Good' to 'Strong' . The wording can be different, but this is the concept. As the bar fills in it should change color from red toward green, becoming stronger green as high confidence is achieved.

We may change other logic later to suggest they stop when confidence reaches some threshold. This should be the confidence based on all of their responses with respect to all rankings of both options and factors.
[comment: created 2026-08-21T03:11:54.155Z | id add-a-your-result-confidence-level-5jjvv2]

## Expanded Description
### agent
During comparison, show a persistent “Current Ranking Confidence Achieved” progress bar that reflects confidence from **all** of the user’s option and factor ranking responses so far (not just the current pair). The bar should advance through stages such as None → Low → Moderate → Fair → Good → Strong (wording can vary) and shift color from red toward a stronger green as it fills. This work is display-only; later we may use the same metric to suggest stopping at a threshold, but that stop logic is out of scope now.

- **Scope:** Comparison-flow UI bar plus a reusable confidence value based on the full ranking set (options and factors).
- **Behavior:** Updates as answers accumulate; six labeled levels; fill and color track the same score.
- **Color:** Red at low confidence, interpolating to stronger green at high confidence.
- **Out of scope:** Changing comparison/ranking logic or prompting the user to stop at a threshold.
- **Open:** Exact formula (coverage vs consistency vs completeness), bar placement in the comparison UI, and whether labels are shown on the bar, as a caption, or both.
[comment: expand completed 2026-08-21T03:27:44.349Z | via executor-opencode | entryId e-20260821-0003 | artifacts: ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T03-26-54-855Z-expand-ltxg42.request.md, ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T03-26-54-855Z-expand-ltxg42.response.md, ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T03-26-54-855Z-expand-ltxg42.trace.log, ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T03-26-54-855Z-expand-ltxg42.result.json]


## Plan
### agent
I'll inspect the comparison flow and ranking logic so the plan matches how confidence should be computed and shown.I'll query the existing graph and inspect ranking/comparison UI next.# Add “Current Ranking Confidence Achieved” bar

Display-only. Live, personal ranking quality from **all option and factor comparisons so far**. Do not change pair scheduling, Results metrics, or stop-at-threshold behavior.

Today: `probe.vue` and `ShareVoteSession.vue` already show **This group** and **Overall** (count vs min passes). Share complete-view uses `metricLabel()` on server `submitter_summary.confidence` (multi-pass only). Project Confidence in `vote_ranking.py` is multi-participant — **not** this bar. Client only holds the current group plus same-channel `prior_pairings`.

---

## 1. Implementation steps

1. **Add `client/utils/rankingConfidence.ts`** (pure, tested)
   - Input: every channel’s pairings (option-under-factor + factor-vs-factor if ≥2 factors), item ids, ranking target.
   - Output: `{ value: 0–1, level, label, color }`.
   - **Score (recommended):** equal-weight mean of per-channel scores:
     - **Coverage ~70%** — decisive pairs (`winner`/`tie`) ÷ pairs needed for that channel’s target (`question_budget` / connected ranking). `unsure`/`skip` do not add coverage.
     - **Consistency ~20%** — repeated-pair agreement, else same-channel multi-pass JS agreement when ≥2 rank orders exist; **omit** this term on first pass (don’t force None).
     - **Decisiveness ~10%** — top-vs-next gap from existing `fitProvisionalScores()` in `pairScheduler.ts`.
   - Missing factor ranking (multi-factor) keeps the mean from reaching Strong.
   - Map to six levels: **None / Low / Moderate / Fair / Good / Strong** (None at 0; then ~20% bands). Do **not** reuse or change `metricLabel()` (Sparse/Early/Building/Solid/Strong on Results).
   - Color: interpolate `--pc-danger` → `--pc-warning` → `--pc-success` from `value`.

2. **Hydrate full ranking set**
   - Small session accumulator (composable or runner-adjacent): completed groups this visit + current `runner.answers` (update on answer/undo).
   - Add compact `progress.ranking_evidence` on next-group / partial-flush payloads (`vote_sort_session.py` + vote/share APIs): `{ group_type, criterion_id, pass_index, item_ids, pairings }[]` for this participant.
   - Resume/reload: seed accumulator from that snapshot so confidence isn’t session-memory-only.
   - Do not recompute project Confidence or change ranking math.

3. **UI: `RankingConfidenceBar.vue`**
   - Persistent strip **above** the existing This group / Overall cards (both comparison surfaces).
   - Caption **Current ranking confidence** + current level on the right; fill + tick labels (or ends + current).
   - Custom fill (not a third identical `soft-card` primary/secondary bar). `prefers-reduced-motion`: no width/color animation.
   - Visible during active compare, group intro, and pause. Hide on access gate and thank-you (share complete already shows a different confidence line).

4. **Wire** `probe.vue` and `ShareVoteSession.vue` to the same component/util. Leave Overall/This group as-is.

5. **Tests:** `client/utils/rankingConfidence.test.ts` (node:test, same pattern as `ranking.test.ts`) — empty→None; options-only vs options+factors; unsure doesn’t inflate; undo drops score; six-level boundaries. Light API test that `ranking_evidence` is present and scoped to the participant.

6. **Copy/docs:** comparison UI only. Do not fold Results Agreement/Repeatability/Stability into this number (`terminology_dictionary.md`). Optional one-line note in `algos.md` that session ranking confidence is display-only and separate from Results Confidence.

---

## 2. Clarifying questions

1. Confirm this is **this participant’s** ranking quality, not project-level Results Confidence.
2. Show on **both** logged-in Compare (`probe.vue`) and share Compare (`ShareVoteSession.vue`)?
3. Keep the six labels as specified, even though Results uses Sparse/Early/Building/Solid/Strong?
4. Should **unsure/skip** only fail to raise the bar, or actively lower it?
5. Keep the bar on pause / group intro / “maximum comparisons” screens?
6. Any required formula, or is the coverage-led blend below acceptable?

---

## 3. Options, trade-offs, recommendation

| | Approach | Pros | Cons |
|---|---|---|---|
| **A** | Reuse Overall % (comparisons / min target) | Trivial | Duplicate bar; not ranking quality; can’t later gate stop |
| **B** | Server participant `confidence` (multi-pass) | Already exists | Stays ~0 until pass 2; ignores in-group answers; not factor+option coverage |
| **C** | Client coverage+consistency+decisiveness over **all** option and factor channels; server sends evidence snapshot | Matches brief; live per answer; reusable for a future stop threshold | New util + small payload |
| **D** | Server score on every answer | Single formula in Python | Chatty; bar lags without a request per click |

**Recommend C.** Placement: full-width meter above the two existing cards, **label + fill** (not ticks-only). Formula: coverage-led blend so the bar moves from the first decisive answers, but Strong requires both option and factor rankings (when factors exist) plus some consistency/decisiveness — so it is not a second progress counter.

Out of scope: stop-when-strong prompts, changing `project_metrics` / `metricLabel`, changing pair selection.
[comment: plan completed 2026-08-21T10:32:29.912Z | via executor-opencode | entryId e-20260821-0001 | artifacts: ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T10-28-17-777Z-plan-3fu8nz.request.md, ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T10-28-17-777Z-plan-3fu8nz.response.md, ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T10-28-17-777Z-plan-3fu8nz.trace.log, ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T10-28-17-777Z-plan-3fu8nz.result.json]


## Build Summary
### agent
I'll inspect the comparison flow, ranking confidence, and related APIs so the bar matches existing ranking evidence.I have the comparison surfaces and scoring inputs; next I’ll add the confidence util, evidence payload, and the bar UI.**bfe6c6b** Add current ranking confidence bar to the compare flow

Display-only compare-session meter (None→Strong, red→green) from this participant’s option and factor pairings. Resume via `progress.ranking_evidence`. Results Confidence unchanged. Version 0.7.66. Static client rebuilt.

Touch points:
- `client/utils/rankingConfidence.ts:427` score (coverage 70 / consistency 20 / decisiveness 10)
- `client/utils/rankingConfidence.test.ts` empty→None, bands, unsure, undo, multi-factor cap
- `client/components/RankingConfidenceBar.vue:1` meter UI
- `client/composables/useRankingConfidence.ts:12` live overlay + seed
- `client/pages/projects/[id]/probe.vue:58` logged-in Compare
- `client/components/ShareVoteSession.vue:143` share Compare
- `src/utils/vote_sort_session.py:445` `build_progress`; `:562` `ranking_evidence_from_groups`
- `src/api/app_project_vote_events.py:524` / `src/api/app_shared_link_ext_access.py:699` partial-flush evidence
- `src/tests/test_project_votes.py` evidence present and participant-scoped
[comment: build completed 2026-08-21T12:09:37.243Z | via executor-opencode | entryId e-20260821-0002 | artifacts: ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T11-55-22-571Z-build-567c0l.request.md, ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T11-55-22-571Z-build-567c0l.response.md, ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T11-55-22-571Z-build-567c0l.trace.log, ./add-a-your-result-confidence-level-5jjvv2/2026-08-21T11-55-22-571Z-build-567c0l.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T12:09:37.243Z build completed (e-20260821-0002)
- 2026-08-21T10:32:29.912Z plan completed (e-20260821-0001)
- 2026-08-21T03:27:44.349Z expand completed (e-20260821-0003)
- 2026-08-21T03:11:54.155Z created (source: user)
