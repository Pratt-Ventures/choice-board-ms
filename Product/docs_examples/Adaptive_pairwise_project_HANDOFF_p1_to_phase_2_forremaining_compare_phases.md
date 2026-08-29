# Handoff: remaining Compare / Results phases

Start this in a **new session**. Phase 1 (adaptive compare) is shipped. Do **not** re-litigate Phase 1 decisions unless a bug forces it.

Canonical math for later reporting: `docs_examples/Implementation Specification for Paired Adaptive question process.md`.  
User-facing language: `docs_examples/terminology_dictionary.md`.  
Current Results (still live, to be replaced in Phase 2): `docs_examples/algos.md` + `src/utils/vote_ranking.py`.

---

## 0. Locked product decisions (do not reopen)

| Topic | Decision |
|-------|----------|
| Group composition | One factor (or overall / factor-importance) per group. If FJ(n) > project question budget, **split into batches**. Pass 1 covers every option **across batches**, not inside one batch. |
| Question budget | Per-project `option_questions_per_group` and `factor_questions_per_group`. Default **20**. UI range `[⌈FJ(n)/2⌉, FJ(n)×2]`, also capped at `C(n,2)` unique pairs. Advanced tab only. |
| FJ formula | `Σ_i ceil(log2(3i/4))` — `ford_johnson_budget` in `src/utils/sort_compare.py` and `client/utils/sortCompare.ts`. Budget only; **not** used to rank. |
| Soft answers | Keep About equal / Not sure / Skip. **Do not invent winners.** `winner` and `tie` inform the model; `unsure`/`skip` consume budget only. |
| n=3 / n=4 | Relax consecutive-item adjacency **only when no legal pair remains**. Never repeat an unordered pair inside a group. |
| Ranking modes | Replace Pick one / Rank all. Internally `winner` \| `top_n` \| `full`. UI: Find Best, Find Top 3 (n≥6), Find Top Half (`floor(n/2)`), Rank All. **No bottom-15% elimination.** Factor-importance groups always `full`. |
| Exclusive sync | `ranking_mode == find_best` ⇒ `project_exclusive_mode = true`, else false (labels / old report code). |
| Persistence | Group row written **when issued**. `group_token` = 10 url-safe chars (not DB id). Partial save after 5 answers or 90s idle (`COMPARE_PARTIAL_*` in `src/config/config_settings.py`). Resume = longer of localStorage vs server pairings. |
| Client vs server | Client **only** sequences pairs (`client/utils/pairScheduler.ts`). Server owns all displayed statistics. |
| **Phase 2 inference** | **Regularized hierarchical Bradley–Terry + Laplace (Gaussian) posterior.** Not NUTS/MCMC on the request path. Keep a sampler-shaped interface (`score_samples[S, items]`) so MCMC can replace the approximator later **without API churn**. |

### Why Laplace, not MCMC, for first ship

Full hierarchical NUTS on every Results/dashboard hit is the latency risk: seconds to tens of seconds once participants × factors × options grow, plus sampler warmup and occasional divergences.

Laplace (MAP + Hessian, or a cheap variational Gaussian) on the same hierarchical BT model:

- Recovers the **same ranking, pairwise P(i>j), p_best, top-N membership, and factor weights** to well within UI precision for typical project sizes.
- Is usually **10–100× faster** (tens of ms to a few hundred ms vs multi-second MCMC).
- Produces draws by sampling `N(θ̂, H⁻¹)`, so every spec aggregator in §§24–47 still runs unchanged.

Known gaps (accept for v1, document in diagnostics):

- Credible intervals can be **slightly too narrow** in very small samples.
- Multimodal / polarized participant clusters are **smoothed** toward a unimodal Gaussian.
- Lapse/`κ` tails are less faithfully estimated than with NUTS.

Do **not** block Compare on inference. Cache by an exact comparison-data version. Optional later: MCMC only for “export / final report” if calibration shows Laplace is not enough.

---

## 1. What Phase 1 already shipped (do not rebuild)

Current app version at handoff: **0.7.42**.

### Compare lifecycle

- `projectvotegroupresult` is created on issue (`status=in_progress`), completed on submit.
- New columns: `group_token`, `status`, `requested_pairing_count`, `received_pairing_count`, `historical_pairing_count`, `ranking_target`, `top_n`, `batch_index`.
- Migrations: `p7q8r9s0t1u2` (questions per group), `q8r9s0t1u2v3` (adaptive groups + `ranking_mode`).
- Session: `POST /ws/project-votes/save-group`, existing `complete-group` / `next-group` / `my-vote`.
- Share: `POST /ext-ws/share/{t}/vote/save-group` plus existing complete/next.

### Scheduler (client)

- `client/utils/pairScheduler.ts` — provisional BT, I×T×R×E×G, coverage, adjacency relaxation, seeded undo.
- `client/composables/useSortGroupRunner.ts` — localStorage key `power-choice:v1:group:{token}`, partial package, no FJ pair picking.
- Soft answers do not drive `id_asc` invented order for scheduling (legacy `effective_rule` may still appear on some pairing dicts; ignore it).

### Project settings

- `CustomerProject.ranking_mode`: `find_best` \| `find_top_3` \| `find_top_half` \| `rank_all`.
- `option_questions_per_group`, `factor_questions_per_group` (default 20).
- Advanced UI + decision-mode toggle on `client/pages/projects/[id]/edit.vue`.

### Results today (still old)

- Authoritative path is still **mean ranks of completed group `rank_order`**, not pooled pairings.
- `vote_ranking._groups()` already **drops `in_progress`** rows.
- `algos.md` still says pairwise Bayesian is retired — Phase 2 reverses that for reporting (pairings become the source of truth).

### Key files

| Area | Path |
|------|------|
| Issue / budget / ranking target | `src/utils/vote_sort_session.py` |
| FJ + clamps | `src/utils/sort_compare.py` |
| Group CRUD | `src/db/models/project_vote_events.py` |
| Session API | `src/api/app_project_vote_events.py` |
| Share API | `src/api/app_shared_link_ext_access.py` |
| Current Results | `src/utils/vote_ranking.py` |
| Client scheduler | `client/utils/pairScheduler.ts` |
| Compare runner | `client/composables/useSortGroupRunner.ts` |
| Settings | `src/config/config_settings.py` |

---

## 2. Phase 2 — Authoritative statistics (Laplace hierarchical BT)

**Goal:** All displayed Results come from pooled **active pairings** (complete groups; optionally include in-progress pairings as real evidence — include them, they are answered). Stop using group `rank_order` for aggregate order. Keep returning a per-group provisional ranked list for back-compat.

**Out of scope:** New dashboard chrome beyond what the existing Results page needs to consume the new payload; dwell-time weighting; temporal decay; pair-specific intransitive extras.

### 2.1 Engine shape

One generic pairwise engine. Reuse for:

1. Options under each factor (and overall-only).
2. Factor importance (same model; softmax latent → weights).
3. Multi-participant hierarchy (`μ + u_p`).
4. Multi-factor combine: `U = Σ_f w_f Q_f` on **posterior draws**, then rank.

Suggested layout (new, do not bloat `vote_ranking.py` further):

```
src/utils/bt_inference/
  model.py          # likelihood, hierarchy, lapse/κ (shrink hard)
  laplace.py        # MAP + Hessian + draw N(θ̂, Σ)
  ranks.py          # posterior_ranks / rank_summary from spec §51
  multifactor.py    # softmax weights × Q_fi, spec §52
  cache.py          # key = hash(project_id, pairing version)
  interface.py      # build_report_v2(...) public entry
```

Keep `vote_ranking.build_report` as a thin adapter that calls `build_report_v2` once tests pass, **or** add a parallel payload field and switch the client in the same PR. Prefer one report object so the UI does not dual-read.

**Stack:** NumPy + SciPy (`optimize`, `linalg`). Do **not** add PyMC/NumPyro for this phase. No new heavy deps unless already in Poetry.

### 2.2 Likelihood (minimum viable hierarchical BT)

For pair (i,j) from participant p under factor f:

```
P(i>j) = (1-λ) σ(κ (θ_pfi - θ_pfj)) + λ/2
```

- `θ_pfi = μ_fi + u_pfi` with `u` hierarchical, strong shrinkage.
- `λ`, `κ` **population-level first** (or one shared pair). Only add per-participant noise params if a participant has enough pairs; otherwise freeze at population.
- Ties (`response=tie`): treat as 0.5/0.5 or an explicit tie likelihood — pick one and test. Unsure/skip: **exclude** from likelihood.
- Identifiability: sum-to-zero on `μ` per factor.
- Left/right bias `β_L` optional; include if cheap (we store `presented_left_id`).
- Do **not** weight by dwell time.

Draw `S` samples (e.g. 400–800) from the Laplace Gaussian. Feed `score_samples` into the spec’s `posterior_ranks` / `rank_summary`.

### 2.3 What to compute (ship this set; hide the rest behind `diagnostics`)

Per option (and per factor-option):

- consensus rank, expected rank, median rank
- `p_exact_rank`, `p_best`, `p_top_n`
- 95% rank CI, rank entropy
- pairwise win strength `Q_i`

Coherence / stability (spec §§30–36, implement the cheap ones first):

- directional pair coherence, expected pair agreement
- participant–consensus Kendall
- top-N Jaccard
- same-winner / same top-N repeat probability from posterior predictive
- max single-participant influence (leave-one-out **approx** from Laplace, not full refits)

Factors:

- expected / median weight + 95% CI
- P(most important), importance rank
- discrimination `SD_i(Q_fi)`, leverage `w D`, normalized leverage
- do **not** call pairwise factor comparisons “ratio-scale importance”

Multi-factor overall: posterior `U_i` ranks and the same rank summaries.

Group `rank_order` is **display-only / back-compat**. Aggregate order = complete pairing pool.

Old groups with empty pairings: fall back to stored `rank_order` as if it were a full set of adjacent winner pairs, or omit from the likelihood and keep a “legacy rank-only” note in diagnostics. Prefer pairings whenever present.

### 2.4 Caching and latency

- Cache key: `project_id` + hash of `(participant_id, group_id, pairing sequence, response)` for all **complete + in-progress** pairings used.
- Invalidate on `save-group` / `complete-group` / mark-complete.
- Compute **on report/dashboard request**, never inside Compare.
- If cache miss would exceed ~500ms on a large project, return last cache + `stale: true` and refresh in-process (or skip stale and just compute — Laplace should usually be fine).
- Do not start a watcher job for this unless measurement shows a problem.

### 2.5 API

Revise the existing `project-report` / share `report` payloads. Keep field names stable where possible (`option_ranking`, `factor_ranking`, scores in [0,1]). Add, don’t rename:

- `p_best`, `p_top_n`, `rank_ci95`, `expected_rank`
- `coherence`, `stability`, `factors[].weight_ci95`, `leverage`
- `diagnostics` (model fit, coverage, left/right, cache age)

Session + share surfaces. After tests pass: `./scripts/extract_openapi/update_openapi_json.sh sessions`.

`vote_view` stays **personal** posterior (`μ + u_p`). Full results = population `μ`.

### 2.6 Tests (required)

New module e.g. `src/tests/test_bt_inference.py` (and keep security/tenancy on report endpoints in `test_project_votes.py` / `test_share_ext_access.py`).

Synthetic recovery (spec §56, Laplace-scale):

- strong winner → high `p_best`
- tied leaders → broad uncertainty
- clear top-3 vs uncertain #3/#4
- homogeneous vs polarized participants (do **not** label polarized people as unreliable)
- important-but-flat factor → high importance, low discrimination, modest leverage

Also:

- ties/unsure/skip handling
- in-progress pairings included
- cache hit does not recompute
- cross-tenant report still 403
- old `rank_order`-only groups do not crash

Do **not** require MCMC ESS/R-hat tests.

### 2.7 Docs to update in the same change

- `docs_examples/algos.md` — state that aggregate Results are hierarchical BT + Laplace; group `rank_order` is no longer the merge source.
- Terminology: keep Confidence, Agreement, Repeatability, Stability, Factor confidence, Decision leverage, Model quality **separate**. No single fake score.

Bump `settings.VERSION` last segment.

---

## 3. Phase 3 — Results / dashboard visualization

**Start only after Phase 2 report payload is stable.**

### 3.1 Principles

- Do not collapse to one “confidence” number.
- Distinct concepts (spec §49): Ranking confidence, Participant agreement, Repeatability, Basket stability, Factor confidence, Decision leverage, Model quality.
- Novice copy from `terminology_dictionary.md` (Agreement not Coherence; Recommended option / Top option by mode).
- `vote_view` = personal only. Full results / in-app Results = population + optional participant drill-down (already have pivot).

### 3.2 First visual increment (ship this)

Existing pages: `client/pages/projects/[id]/results.vue`, `client/pages/share/report/[token]/index.vue`, helpers `client/utils/ranking.ts`.

Add, matching current visual language (do not restyle the whole app):

1. Rank list: score bar + **rank CI** + `p_best` or `p_top_n` depending on `ranking_mode`.
2. Factor table: Importance / Differentiation / Decision leverage (spec §44).
3. Separate metric chips: Agreement, Repeatability, Stability (not one blended Confidence).
4. Polarizing option hint when participant rank SD is high (`Option A: consensus #2, highly polarizing`).
5. “Preliminary” vs “Final” stays tied to completion, not to Laplace vs MCMC.

### 3.3 Second visual increment (if time)

- Pairwise dominance / close-call explanation (`P(i>j)`).
- Leave-one-participant influence flag.
- Factor contribution to an option (`w_f (Q_fi - 0.5)`).
- Diagnostics drawer for admins only (calibration, coverage, left/right, cache).

After `client/` changes: `./scripts/nuxt/update_static_client.sh` must succeed.

### 3.4 Tests

API tests already cover payload. Add/adjust any Results mapping unit helpers if `ranking.ts` grows. No need for Playwright unless a flow breaks (share report still loads).

---

## 4. Explicitly later (not Phase 2 or 3)

- PyMC / NumPyro NUTS on the live path (optional “final report” job only if Laplace calibration fails).
- Dwell-time as reliability weight (diagnostic only until it improves held-out repeat prediction).
- Pass/time decay.
- Pair-specific intransitive / cycle model (track cycle rate in diagnostics; do not switch the likelihood).
- Dropping `project_exclusive_mode` column (keep synced).
- Client scheduler look-ahead polish beyond what Phase 1 already does.

---

## 5. How a new session should start

1. Read this file, `AGENTS.md`, spec §§20–52 and §57, `terminology_dictionary.md`.
2. Skim `src/utils/vote_ranking.py` (`build_report`) and current report JSON used by `results.vue`.
3. Implement Phase 2 engine + wire `build_report` + tests + OpenAPI + version bump.
4. Only then Phase 3 UI.
5. If anything in the report contract or tenancy is unclear, **stop and ask** before migrations or published `static_client/`.

### Suggested first commit of Phase 2

Laplace BT on a single factor, one participant, returning `rank_summary` — tested against a known synthetic order — with no UI change. Then hierarchy, then multi-factor, then swap `build_report`.
