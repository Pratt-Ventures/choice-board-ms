# Completed: Adaptive pairwise Compare + Results

**Status:** Phases 1–3 shipped.  
**App version at close:** `0.7.44`  
**Date:** 2026-08-19

This is the close-out record for converting Compare and Results from Ford–Johnson group `rank_order` merge to adaptive pairwise selection plus hierarchical Bradley–Terry inference. Do **not** reopen locked decisions unless a bug forces it.

Canonical math: `Implementation Specification for Paired Adaptive question process.md`  
User-facing language: `terminology_dictionary.md`  
Authoritative Results math: `algos.md`  
Phase plans (historical): `HANDOFF_remaining_compare_phases.md`, `HANDOFF_phase3_results_ui.md`

---

## 1. What shipped

| Phase | What | Version at handoff / ship |
|-------|------|---------------------------|
| **1** | Adaptive Compare: pair scheduler, group lifecycle, ranking modes, question budget | **0.7.42** |
| **2** | Hierarchical BT + Laplace inference; pairings are the aggregate source of truth | **0.7.43** |
| **3** | Results / Full results UI consumes the new posterior fields (first visual increment) | **0.7.44** |

Compare collects pair outcomes. Results ranks from the pooled pairing likelihood. The UI shows uncertainty as separate concepts, not one Confidence number.

---

## 2. Locked decisions (do not reopen)

| Topic | Decision |
|-------|----------|
| Group composition | One factor (or overall / factor-importance) per group. If FJ(n) > question budget, **split into batches**. Pass 1 covers every option **across batches**. |
| Question budget | `option_questions_per_group` / `factor_questions_per_group`. Default **20**. UI range `[⌈FJ(n)/2⌉, FJ(n)×2]`, also capped at `C(n,2)`. Advanced tab only. |
| FJ formula | `Σ_i ceil(log2(3i/4))` — **budget only**, not used to rank. |
| Soft answers | About equal / Not sure / Skip stay. Do **not** invent winners. `winner` and `tie` inform the model; `unsure`/`skip` consume budget only. |
| n=3 / n=4 | Relax consecutive-item adjacency **only when no legal pair remains**. Never repeat an unordered pair inside a group. |
| Ranking modes | `find_best` \| `find_top_3` \| `find_top_half` \| `rank_all`. Factor-importance groups always full. `find_best` ⇔ `project_exclusive_mode = true`. |
| Persistence | Group row written **when issued**. `group_token` = 10 url-safe chars. Partial save after 5 answers or 90s idle. Resume = longer of localStorage vs server pairings. |
| Client vs server | Client **only** sequences pairs. Server owns all displayed statistics. |
| Inference | Regularized hierarchical BT + **Laplace** (not live MCMC). Draws stay `score_samples[S, items]`. |
| Aggregate source | Pooled **pairings** (complete + in-progress). `rank_order` is display-only / legacy fallback. |
| Metrics | Do **not** collapse to one Confidence number. |
| Copy | **Agreement** (not Coherence). **Recommended option** when `find_best`; **Top option** otherwise. Preliminary vs Final = **completion**, not Laplace vs MCMC. |
| `vote_view` | Personal posterior only. In-app Results / share Full results = population + pivot drill-down. |
| Field names | Add, don’t rename JSON. `score` stays [0, 1]. |
| Visual language | Match existing Results chrome. Do not restyle the app. |

---

## 3. Phase 1 — Adaptive Compare

### Lifecycle

- `projectvotegroupresult` created on issue (`status=in_progress`), completed on submit.
- Columns: `group_token`, `status`, `requested_pairing_count`, `received_pairing_count`, `historical_pairing_count`, `ranking_target`, `top_n`, `batch_index`.
- Migrations: `p7q8r9s0t1u2` (questions per group), `q8r9s0t1u2v3` (adaptive groups + `ranking_mode`).
- Session: `POST /ws/project-votes/save-group` plus `complete-group` / `next-group` / `my-vote`.
- Share: `POST /ext-ws/share/{t}/vote/save-group` plus existing complete/next.
- Partial flush: `COMPARE_PARTIAL_FLUSH_COUNT=5`, `COMPARE_PARTIAL_IDLE_SECONDS=90`.

### Scheduler (client)

- `client/utils/pairScheduler.ts` — provisional BT, I×T×R×E×G, coverage, adjacency relaxation, seeded undo.
- `client/composables/useSortGroupRunner.ts` — localStorage `power-choice:v1:group:{token}`, partial package, no FJ pair picking.
- Soft answers do not invent an `id_asc` winner for scheduling.

### Project settings

- `CustomerProject.ranking_mode`: `find_best` \| `find_top_3` \| `find_top_half` \| `rank_all`.
- `option_questions_per_group`, `factor_questions_per_group` (default 20).
- Advanced UI + decision-mode toggle on `client/pages/projects/[id]/edit.vue`.

### Key files

| Area | Path |
|------|------|
| Issue / budget / ranking target | `src/utils/vote_sort_session.py` |
| FJ + clamps | `src/utils/sort_compare.py` |
| Group model | `src/db/models/project_vote_events.py` |
| Session API | `src/api/app_project_vote_events.py` |
| Share API | `src/api/app_shared_link_ext_access.py` |
| Client scheduler | `client/utils/pairScheduler.ts` |
| Compare runner | `client/composables/useSortGroupRunner.ts` |

---

## 4. Phase 2 — Hierarchical BT + Laplace

`src/utils/vote_ranking.build_report` is a thin adapter → `src/utils/bt_inference.interface.build_report_v2`.

```
src/utils/bt_inference/
  model.py          # likelihood, hierarchy, lapse/κ, left/right
  laplace.py        # MAP + Hessian + N(θ̂, H⁻¹) draws
  ranks.py          # posterior_ranks / rank_summary (spec §51)
  multifactor.py    # softmax weights × Q_fi (spec §52)
  observations.py   # pairings; unsure/skip excluded; ties 0.5/0.5; rank_order → adjacent pairs
  cache.py          # fingerprint of pairing set
  interface.py      # infer_project + report assembly
```

### Model

```
P(i>j) = (1−λ) σ(κ (θ_pfi − θ_pfj + β_L L)) + λ/2
θ_pfi  = μ_fi + u_pfi
```

- `μ` population latent (sum-to-zero per factor). `u` hierarchical participant deviation, strong shrinkage.
- `λ`, `κ` population-level. Unsure / skip excluded. Ties 0.5/0.5.
- In-progress pairings included (they are answered).
- Multi-factor overall: `U = Σ_f w_f Q_f` on posterior draws (`w = softmax(φ)`).
- Cache key = hash of the pairing set. Compute on report/dashboard request only — never inside Compare.
- Stack: NumPy + SciPy. No PyMC / NumPyro on the live path.

Known Laplace gaps (accepted, surfaced in `diagnostics`): credible intervals can be slightly too narrow in tiny samples; polarized clusters are smoothed toward a unimodal Gaussian; lapse/`κ` tails are less faithful than NUTS.

### Payload (add, don’t rename)

Stable old fields remain: `option_ranking`, `option_ranking_equal`, `factor_ranking`, `by_factor`, `participants`, `pivot`, `metrics`, `results`, `score` in [0, 1], 0-based display `rank`, 0-based `mean_rank`.

**Name collisions**

| Key | Type | Meaning |
|-----|------|---------|
| `stability` (top-level and `metrics.stability`) | float 0–1 | Legacy blended chip. **Do not overwrite.** |
| `posterior_stability` | object | `same_winner_repeat_probability`, `same_top_n_repeat_probability`, `max_single_participant_influence` |
| `coherence` (top-level) | object | `directional`, `expected_pair_agreement`, `participant_consensus_kendall`, `top_n_jaccard`, `cycle_rate` |
| `coherence` on a participant row | float 0–1 | Personal vs consensus alignment |
| `confidence` / `metrics.confidence` | float | Legacy blend. Not ranking confidence. |

**Option / factor row additions:** `expected_rank`, `median_rank`, `p_best`, `p_top_n`, `p_exact_rank`, `rank_ci95` (1-based), `rank_entropy`, `pairwise_win_strength`, `participant_rank_sd`, `polarizing`, factor `weight` / `normalizedWeight`, `weight_ci95`, `discrimination`, `leverage`, `p_most_important`.

**Report extras:** `ranking_mode`, `top_n`, `engine: "hierarchical_bt_laplace"`, `diagnostics`.

`vote_view` personal board: `build_personal_submitter_summary` → `build_report` on that participant’s groups only.

Tests: `src/tests/test_bt_inference.py` (strong winner, ties, top-N, polarized participants, legacy rank-only groups, posterior fields). Existing report / share / tenancy suites remain.

---

## 5. Phase 3 — Results UI (first increment)

In-app Results and share Full results consume the Phase 2 payload. Visual language matches existing chrome.

### Rank list

- Score bar (`score` / Q_i) kept.
- Rank CI from `rank_ci95` (1-based, e.g. “ranks 1–3”).
- `p_best` when `ranking_mode == find_best`.
- `p_top_n` when `find_top_3` / `find_top_half`, labeled with `report.top_n`.
- `rank_all`: CI + expected rank only — no fake confidence % from entropy.
- Headline: **Recommended option** (`find_best`) / **Top option** otherwise.
- Polarizing: `{title}: consensus #{expected_rank}, highly polarizing`.

### Factor table (spec §44)

Each factor shows three distinct lines:

| UI label | Field |
|----------|--------|
| Importance | `normalizedWeight` / `weight` (+ `weight_ci95`) |
| Differentiation | `discrimination` |
| Decision leverage | `leverage` |

Do **not** call pairwise factor comparisons “ratio-scale importance”. “Best option by factor” stays as a secondary block.

### Metric chips (not one Confidence)

Primary chips replace the hero confidence ring and the four legacy cards:

| Chip | Source |
|------|--------|
| **Agreement** | `coherence.expected_pair_agreement` |
| **Repeatability** | `same_winner_repeat_probability` (`find_best` / `rank_all`) or `same_top_n_repeat_probability` (`find_top_3` / `find_top_half`) |
| **Stability** | Counterpart posterior number (winner vs top-N). Not legacy `metrics.stability`. |

Null / no-data → “—” / “Not enough comparisons”, not 0%. No fourth chip that averages the three.

`same_top_n` is **not** used when `top_n >= n` (`rank_all`): that probability is identically 1.

Preliminary vs Final stays tied to `metrics.completion >= 95` / project closed.

### Mapping helpers

`client/utils/ranking.ts`: `mapServerRanking` forwards the new fields. Helpers: `normalizeRankingMode`, `headlineOptionLabel`, `formatRankCi`, `optionChanceCaption`, `polarizingCaption`, `insightMetricChips`, `formatNullablePercent`, `formatWeightCi`, `formatExpectedRank`.

Unit tests: `client/utils/ranking.test.ts` (`node --experimental-strip-types --test`).

### Pages

| Area | Path |
|------|------|
| In-app Results | `client/pages/projects/[id]/results.vue` |
| Share Full results | `client/pages/share/report/[token]/index.vue` |
| Mapping | `client/utils/ranking.ts` |

After client changes: `./scripts/nuxt/update_static_client.sh` (succeeded for 0.7.44). `static_client/` is gitignored; published locally.

---

## 6. How data flows now

```
Compare (client pairScheduler)
    → pairings on projectvotegroupresult (complete + in-progress)
    → build_report → build_report_v2 → infer_project
         Laplace hierarchical BT
         rank_summary / multifactor / coherence + posterior_stability
    → project-report / share report JSON
    → mapServerRanking + insightMetricChips
    → Results + Full results UI
```

Group `rank_order` is still written (provisional / back-compat). Aggregate order does **not** come from averaging those lists.

---

## 7. Explicitly later (not in this project)

Phase 3 second visual increment (not shipped):

- Close-call `P(i>j)` / `pairwise_top` on the public report
- `max_single_participant_influence` flag when large
- Factor contribution `w_f (Q_fi − 0.5)`
- Admin-only diagnostics drawer (`diagnostics`: coverage, left/right, cache, lapse)

Later than Phase 3:

- PyMC / NumPyro on the live path (optional final-report job only if Laplace calibration fails)
- Dwell-time weights, pass/time decay, cycle likelihood as the ranking model
- Dropping `project_exclusive_mode` (keep synced with `ranking_mode`)
- Client scheduler look-ahead polish
- Replacing Laplace with MCMC for “final report”

---

## 8. Verify

```bash
src/.venv/bin/pytest src/tests/test_bt_inference.py
src/.venv/bin/pytest src/tests/test_sort_compare.py src/tests/test_project_votes.py -q
node --experimental-strip-types --test client/utils/ranking.test.ts
# GET /status → version 0.7.44
```

No OpenAPI regen was required (report remains an untyped `dict`; no new routes).

---

## 9. Docs map

| File | Role |
|------|------|
| This file | Close-out summary |
| `Adaptive_pairwise_project_HANDOFF_p1_to_phase_2_forremaining_compare_phases.md` | Phase 1 locked table + Phase 2/3 plan |
| `Adaptive_pairwise_project_HANDOFF_p2_to_phase3_results_ui.md` | Phase 3 UI contract |
| `algos.md` | Authoritative Results math (BT + Laplace; legacy merge is display-only) |
| `terminology_dictionary.md` | User-facing copy |
| `Adaptive_pairwise_project_Implementation Specification` | Canonical spec |
