# Handoff: Phase 3 — Results / dashboard visualization

Start this in a **new session**. Phase 1 (adaptive compare) and Phase 2 (Laplace hierarchical BT) are shipped. Do **not** re-litigate those decisions unless a bug forces it.

Canonical math: `docs_examples/Implementation Specification for Paired Adaptive question process.md` §§24–27, §44, §48–49.  
User-facing language: `docs_examples/terminology_dictionary.md`.  
Prior plan (locked product table + Phase 2 engine notes): `docs_examples/HANDOFF_remaining_compare_phases.md`.  
Algo note (Phase 2 is authoritative): `docs_examples/algos.md`.

---

## 0. Locked decisions (do not reopen)

| Topic | Decision |
|-------|----------|
| Inference | Regularized hierarchical BT + Laplace. Not live MCMC. Draws stay `score_samples[S, items]`. |
| Aggregate source | Pooled **pairings** (complete + in-progress). Group `rank_order` is display-only / legacy fallback. |
| Metrics | Do **not** collapse to one Confidence number. Keep Ranking confidence, Agreement, Repeatability, Stability, Factor confidence, Decision leverage, Model quality **separate**. |
| Copy | Agreement (not Coherence) for novices. **Recommended option** when `find_best`; **Top option** / **Leading option** otherwise. Preliminary vs Final = **completion**, not Laplace vs MCMC. |
| `vote_view` | Personal only. In-app Results / share report = population + existing pivot drill-down. |
| Visual language | Match current Results chrome. Do **not** restyle the whole app. |
| Field names | Add, don’t rename JSON. `score` stays [0, 1]. |
| Scope | First visual increment only (below). No dwell-time, no NUTS, no scheduler polish. |

---

## 1. What Phase 2 already shipped (do not rebuild)

Current app version at this handoff: **0.7.43**.

`src/utils/vote_ranking.build_report` is a thin adapter → `src/utils/bt_inference.interface.build_report_v2`.

Engine layout:

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

Tests: `src/tests/test_bt_inference.py` plus existing report suites in `test_vote_ranking_probes.py` / `test_sort_compare.py` / project-votes + share report paths.

### 1.1 Payload contract (consume this)

Stable old fields still present: `option_ranking`, `option_ranking_equal`, `factor_ranking`, `by_factor`, `participants`, `pivot`, `metrics`, `results`, `score` in [0, 1], 0-based display `rank`, 0-based `mean_rank`.

**Name collisions — read carefully:**

| Key | Type now | Meaning |
|-----|----------|---------|
| `stability` (top-level and `metrics.stability`) | **float** 0–1 | Legacy blended chip. **Do not overwrite.** |
| `posterior_stability` | **object** | Spec §35-ish: `same_winner_repeat_probability`, `same_top_n_repeat_probability`, `max_single_participant_influence` |
| `coherence` (top-level) | **object** | Spec §§30–32: `directional`, `expected_pair_agreement`, `participant_consensus_kendall`, `top_n_jaccard`, `cycle_rate` |
| `coherence` on a **participant row** | **float** 0–1 | Personal vs consensus alignment (unchanged) |
| `coherence_method` | string | `spearman` \| `kendall` (unchanged) |
| `confidence` / `metrics.confidence` | float | Legacy blend. Do not treat as ranking confidence. |

**Option / factor row additions** (on `option_ranking`, `by_factor[*]`, often `factor_ranking`):

| Field | Notes |
|-------|--------|
| `expected_rank` | 1-based |
| `median_rank` | 1-based |
| `p_best`, `p_top_n`, `p_exact_rank` | |
| `rank_ci95` | `[lo, hi]` **1-based** ranks |
| `rank_entropy` | |
| `pairwise_win_strength` | = `score` = Q_i |
| `participant_rank_sd`, `polarizing` | options; polarizing hint |
| `weight` / `normalizedWeight` | factors; softmax expected weight |
| `weight_ci95` | `[lo, hi]` |
| `discrimination` | SD_i(Q_fi) |
| `leverage` | normalized L_f^* |
| `p_most_important` | |

**Report extras:**

- `ranking_mode`: `find_best` \| `find_top_3` \| `find_top_half` \| `rank_all`
- `top_n`: resolved from mode + n
- `engine`: `"hierarchical_bt_laplace"`
- `diagnostics`: model, n_samples, coverage, graph_connected, left_right_bias, lapse, kappa, cache_hit, fit_ms, legacy_rank_only_groups, pairings_used, …

`mapServerRanking` in `client/utils/ranking.ts` **does not yet forward** the new fields. Extend it (or add a sibling mapper) so Vue rows carry `p_best`, `p_top_n`, `rank_ci95`, `expected_rank`, `polarizing`, `discrimination`, `leverage`, `weight_ci95`.

Project `ranking_mode` is already injected into report settings via `ranking_settings_with_project_influence`. Share report uses the same `build_report`.

`vote_view` personal board: `build_personal_submitter_summary` → `build_report` on that participant’s groups only (personal fit). Do not show population stats there.

### 1.2 What the UI still shows (replace / split)

`client/pages/projects/[id]/results.vue` still:

- One confidence ring + Stability / Confidence / Factor divergence / Comparisons cards (legacy `metrics.*`)
- Rank rows: score bar + mean rank + group count — **no rank CI, no p_best / p_top_n**
- Factor list: importance bar + old stab/confidence — **no Differentiation / Decision leverage**
- Preliminary vs Final already keyed off `metrics.completion >= 95` (keep that rule)

Share full-results: `client/pages/share/report/[token]/index.vue` is a thinner copy (score bars only). Update in the same increment so owners and guests see the same concepts.

---

## 2. Phase 3 — ship this first increment

**Out of scope:** new dashboard chrome beyond these pages; restyling Vuetify/theme; backend inference changes; OpenAPI unless you add typed response models (report is still `dict`).

### 2.1 Rank list

On each option row (overall ranking, and share ranking):

- Keep score bar (`score` / Q_i).
- Show **rank CI** from `rank_ci95` (1-based, e.g. “ranks 1–3”).
- Show **`p_best`** when `ranking_mode == find_best` (or exclusive / winner).
- Show **`p_top_n`** when mode is `find_top_3` or `find_top_half` (label with the actual N from `report.top_n`).
- For `rank_all`, CI + expected rank is enough; do not invent a fake “confidence %” from entropy unless you also show entropy separately.

Headline: **Recommended option** if find_best / exclusive; **Top option** otherwise (already mostly correct on the in-app hero).

### 2.2 Factor table (spec §44)

Replace or extend “What matters most” so each factor shows three distinct columns/lines:

| UI label | Field |
|----------|--------|
| Importance | `normalizedWeight` / `weight` (+ `weight_ci95` if cheap) |
| Differentiation | `discrimination` |
| Decision leverage | `leverage` |

Do **not** call pairwise factor comparisons “ratio-scale importance”.

Keep “Best option by factor” as a secondary block.

### 2.3 Metric chips (not one Confidence)

Replace the hero ring + four legacy cards as the **primary** story. Keep old `metrics.confidence` / `metrics.stability` out of the main chips (optional advanced/footnote only).

Suggested primary chips (novice names):

| Chip | Source | Spec idea |
|------|--------|-----------|
| **Agreement** | `coherence.expected_pair_agreement` or `coherence.directional` (pick one; prefer expected pair agreement) | Participant agreement |
| **Repeatability** | `posterior_stability.same_winner_repeat_probability` (find_best) or `same_top_n_repeat_probability` (top-N / rank-all) | Same result if the same people compared again |
| **Stability** | same-winner / same-top-N is the basket-style number we have; do **not** reuse legacy `metrics.stability` for this chip | New-group / posterior repeat |

If a value is null (too little data), show “—” / “Not enough comparisons”, not 0%.

Do not add a fourth chip that averages the three.

### 2.4 Polarizing hint

When `polarizing` is true (or `participant_rank_sd` is high), a caption on that option:

`{title}: consensus #{expected_rank or rank+1}, highly polarizing`

### 2.5 Preliminary vs Final

Leave tied to completion (`metrics.completion` / project closed), **not** to Laplace vs MCMC or cache age.

### 2.6 Second increment (only if time)

- Close-call: `P(i>j)` — pairwise matrix is **not** currently on the public report (only internal `inferred.pairwise`). If you need it, add a small `pairwise_top` (leader vs runner-up) in the report payload; do not dump a full n×n unless necessary.
- `posterior_stability.max_single_participant_influence` flag when large.
- Factor contribution `w_f (Q_fi − 0.5)` — not computed as a ready list today; derive later or add server-side.
- Admin-only diagnostics drawer from `diagnostics` (coverage, left/right, cache, lapse). Hide from share guests.

---

## 3. Files to touch

| Area | Path |
|------|------|
| In-app Results | `client/pages/projects/[id]/results.vue` |
| Share full results | `client/pages/share/report/[token]/index.vue` |
| Mapping helpers | `client/utils/ranking.ts` (`mapServerRanking`) |
| Copy / terms | `docs_examples/terminology_dictionary.md` |
| Optional payload add | `src/utils/bt_inference/interface.py` only if you need pairwise-on-leader |
| Version | `src/config/config_settings.py` `VERSION` last segment |

No migration. No `static_client/` commit (gitignored; publish locally).

After **any** `client/` change: `./scripts/nuxt/update_static_client.sh` must succeed.

If you add/change endpoint schemas (unlikely): tests first, then `./scripts/extract_openapi/update_openapi_json.sh sessions`.

Bump `settings.VERSION` (`0.7.43` → `0.7.44`).

---

## 4. Tests

Payload is already covered in `src/tests/test_bt_inference.py`. For Phase 3:

- Extend / add unit helpers next to `mapServerRanking` if mapping grows (CI format, which probability to show by mode).
- No Playwright unless share report or Results fail to load.
- Do not weaken Phase 2 recovery tests.

---

## 5. How this session should start

1. Read this file, `AGENTS.md`, terminology dictionary §7, spec §44 and §49.
2. Skim `results.vue` (hero + rank list + factor card) and `ranking.ts` `mapServerRanking`.
3. Confirm a live `project-report` JSON still has `engine`, `coherence`, `posterior_stability`, and option `p_best` / `rank_ci95` (do not re-fit the model).
4. Implement first increment (mapper → in-app Results → share report → static client → version bump).
5. If a chip source is ambiguous (which coherence field = Agreement), pick **expected_pair_agreement** and note it in UI caption. If you need a field that is not on the report, **stop and ask** before changing tenancy or published `static_client/`.

### Suggested first commit of Phase 3

Forward new fields through `mapServerRanking` and show rank CI + `p_best`/`p_top_n` on the in-app overall ranking only. Then chips, then factor table, then share page.

---

## 6. Explicitly later (not Phase 3)

- PyMC / NumPyro on the live path
- Dwell-time weights, pass decay, cycle likelihood
- Dropping `project_exclusive_mode`
- Client scheduler look-ahead
- Replacing Laplace with MCMC for “final report”
