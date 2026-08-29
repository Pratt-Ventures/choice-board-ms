# Ranked-group Results algorithms

Canonical specification for project Results math.

**Authoritative aggregate Results** (Phase 2): regularized hierarchical Bradley–Terry + Laplace (Gaussian) posterior in `src/utils/bt_inference/`. Pairings are the source of truth. Group `rank_order` is display-only / back-compat and is used only when a group has no pairings (converted to adjacent winner pairs).

Implementation entry: `src/utils/vote_ranking.build_report` → `bt_inference.interface.build_report_v2`.  
Sampler-shaped draws: `score_samples[S, items]` so a later MCMC engine can replace Laplace without API churn.  
UI display helpers: `client/utils/ranking.ts`.

User-facing terms follow `docs_examples/terminology_dictionary.md` (Project · Option · Factor · Compare · Results). Keep Confidence, Agreement, Repeatability, Stability, Factor confidence, Decision leverage, and Model quality **separate** — no single blended score.

Compare-session **Current ranking confidence** (`client/utils/rankingConfidence.ts`) is display-only: this participant’s option and factor pairing coverage, optional consistency, and top-vs-next decisiveness. It is not Results Confidence and is not used to stop comparing.

Math detail: `docs_examples/Implementation Specification for Paired Adaptive question process.md` §§20–52.

---

## 0. Hierarchical BT + Laplace (authoritative)

For pair `(i, j)` from participant `p` under factor `f`:

```
P(i>j) = (1−λ) σ(κ (θ_pfi − θ_pfj + β_L L)) + λ/2
θ_pfi = μ_fi + u_pfi
```

- `μ` is the population latent (sum-to-zero per factor). `u` is a hierarchical participant deviation with strong shrinkage.
- `λ`, `κ` are population-level. Unsure / skip are excluded. Ties are 0.5/0.5.
- In-progress pairings are included (they are answered).
- MAP + Hessian; draws from `N(θ̂, H⁻¹)`. Multi-factor overall is `U = Σ_f w_f Q_f` on those draws (`w = softmax(φ)`).
- Scores in `[0, 1]` are pairwise win strength `Q_i`. Added fields: `p_best`, `p_top_n`, `rank_ci95`, `expected_rank`, `coherence`, `posterior_stability`, `diagnostics`.
- Cache key = hash of the pairing set used. Compute on report/dashboard request only.

The sections below document the **legacy mean-rank merge** still used for some display helpers (influence labels, multi-pass chips) and for reconstructing a provisional group order. They are **not** the aggregate ranking source.

---

## 1. Inputs

Votes are stored as sort groups (`ProjectVoteGroupResult`). Aggregate inference uses **pairings** (complete + in-progress). `rank_order` is provisional.

| Field | Meaning |
|-------|---------|
| `group_type` | `alternative` (options) or `criteria` (factors) |
| `criterion_id` | Factor id for option sorts; `null` = overall options or factor-ranking group |
| `pass_index` | 1-based multi-pass index |
| `rank_order` | Item ids **best → worst** (position 0 = rank 0 = best) |
| `comparison_count` | Pairs used inside the sort UI (audit / influence mass only) |
| `pairings` | Pair outcomes from the sort UI; used to **repair** `rank_order` when present |

Group kinds:

1. **Options by factor** — `alternative` + `criterion_id`
2. **Options overall** — `alternative` + null criterion (no factors / overall-only)
3. **Factors** — `criteria` (+ null criterion)

---

## 2. Rank maps and mean ranks

```
effective_rank_order(group):
  if stored rank_order is a full permutation AND consistent with hard pairings
    (every winner ranked before its loser) → stored rank_order
  else if pairings present → Copeland reconstruction (wins − losses, …)
  else → stored rank_order
rank_order_to_map(order): item_id → position index   # 0 = best
mean_rank_maps(list of maps): item_id → average rank across maps
```

Missing items in a map are omitted from that map’s average (not imputed).

Preferring a consistent stored order matters: FJ pairings are a **path-dependent
subset**, so Copeland on that graph alone can reorder mid/low items (e.g. reverse
axis `5,4,3,2,1` → `5,4,3,1,2`) even when the client total order is correct.

### Sort UI (Ford–Johnson) — best→worst

Losers of a paired winner **W** must insert at index **> index(W)** only.
A prior bug inserted losers in `[0, index(W))`, which could place a known-worse
item first. Fixed in `client/utils/sortCompare.ts`. Historical rows whose stored
order **violates** a pairing (winner after loser) are repaired via Copeland on
`pairings` in `effective_group_rank_order` (do not re-run FJ on stored pairings —
the comparison set is path-dependent).

### Per participant (`participant_rank_bundle`)

1. Split groups into factor-ranking maps vs option maps keyed by `criterion_id`.
2. Mean ranks within each bucket (multi-pass averages).
3. **Factor weights** from factor mean ranks (see §3).
4. **Overall option ranks** = weight-averaged mean ranks across factors  
   (`weighted_option_ranks`). If only an overall (null-criterion) bucket exists, use it directly. If factor importance is missing but multiple factor buckets exist, use **equal** factor weights.
5. **Equal-weight overall** = same merge with equal factor weights (`option_ranking_equal`).

---

## 3. Scores and factor weights (display)

All public `score` fields are **normalized preference in \[0, 1\]**.

```
preference(mean_rank, n) = max(0, (n − 1) − mean_rank)     # Borda-style
score(mean_rank, n)      = preference / (n − 1)             # n = 1 → 1.0
```

- Best possible mean rank 0 → score 1.0  
- Worst mean rank n−1 → score 0.0  
- UI: `formatPercent(score)` → `round(score × 100)%` (never multiply rank-distance)

**Factor importance weights** (sum to 1):

```
alpha    = project.factor_weight_floor_alpha   # default 0.5, clamp 0.1–0.9
floor    = alpha × (n − 1)                    # n-invariant top/bottom ratio (1+α)/α
raw_i    = preference(rank_i, n) + floor
weight_i = raw_i / Σ raw
```

- Default `alpha = 0.5` → two clear ranks yield **75% / 25%** (same as the historic fixed `+0.5` floor).
- Lower alpha → more spread; higher alpha → more equal.
- Not stored on templates; project setting only.

Emitted on factor rows as `normalizedWeight` / `weight`, and as `factor_weights` map.

Entries also include `mean_rank`, `rank` (0-based order), `preference`, and `data_points` (supporting group/comparison counts).

---

## 4. Project-level merge

Participants are merged with **influence mass**:

```
β = { comparisons: 1.0, balanced: 0.5, participants_normalized: 0.1 }[mode]
n_eff = max(n_comp, n_min)          # n_min default 10, clamp 3–500
unit_weight w = n_eff^(β − 1)       # per-comparison unit
influence     = w × n_comp          # total mass  (≈ n^β when n ≥ n_min)
```

Weighted mean rank for item k:

```
rank_k = Σ_p (influence_p × rank_{p,k}) / Σ_p influence_p   # over participants who ranked k
```

Applied separately to overall (adjusted), overall (equal factors), factors, and each by-factor option ranking.

---

## 5. Distributions for information metrics

Convert a rank map to a preference distribution (probability simplex):

```
p_i ∝ preference(rank_i, n) + ε
p   = normalize(p)
```

**Jensen–Shannon divergence** (symmetric KL) between distributions p, q:

```
m = (p + q) / 2
JS(p, q) = ½ KL(p ‖ m) + ½ KL(q ‖ m)     # range [0, ln 2]
agreement(p, q) = 1 − JS(p, q) / ln 2    # range [0, 1]
```

Multi-distribution agreement = mean pairwise `agreement`.

**Top-half distribution** (for stability):

```
k = max(1, ceil(fraction × n))   # fraction default 0.5
keep the k best items by rank
renormalize their preference mass
```

---

## 6. Stability (same-channel, across people)

**Never** compare one factor’s option list to another factor’s list for stability.
Divergence across factors is expected and is measured separately as **Factor divergence** (§7).

**Channels** (compared only to the same channel on other participants):

1. Factor-importance rankings (`criteria` groups)  
2. Option rankings under factor F (`alternative` + `criterion_id = F`)  
3. Overall option rankings when no factors (`alternative` + null criterion)

```
For each channel with ≥2 participants who have that channel:
  score_c = mean pairwise JS-agreement of top_half_dist(rank_map)
stability = mean of score_c over channels that qualify
stability_basis = "cross_participant"
```

- Emphasizes agreement on **who is in the lead pack** within each channel.  
- **One participant:** no peer channel → fall back to multi-pass consistency  
  (`stability_basis = "multi_pass"`).  
- No data → 0, `stability_basis = "none"`.

Per-factor UI “stability” = same-channel option-list agreement for that factor only  
(or that factor’s multi-pass consistency when alone).

---

## 7. Factor divergence (landscape split)

How differently **factors** rank **options** (collinearity inverse).  
Uses **Spearman ρ** on mean-rank maps (not JS on soft masses), so pure order
disagreement — different #1s under different factors — surfaces clearly.

```
For each pair of factors F_i, F_j with option rank maps:
  ρ_ij = spearman(rank_map_i, rank_map_j)     # ∈ [−1, 1]
  d_ij = (1 − ρ_ij) / 2                       # 0 = identical, 1 = fully reversed
factor_divergence = mean d_ij
```

High divergence is **normal and insightful** when factors measure different things.
It is **not** a stability penalty.

---

## 8. Confidence

**Definition:** multi-pass consistency + inter-participant agreement + sample depth.  
Does **not** punish cross-factor disagreement.

### Multi-pass (same channel only)

```
For each (group_type, criterion_id) with ≥2 completed passes:
  include pairwise JS-agreement of full rank distributions
multi_pass = mean of those pair agreements
```

No multi-pass anywhere → 0. **Never** substitutes cross-factor option lists.

### Inter-participant

```
agreement = mean pairwise JS-agreement of full overall preference distributions
```

With **&lt; 2 participants**, confidence uses `multi_pass` in place of peer agreement  
(no artificial agreement = 1.0).

### Depth

```
expected_groups ≈ (n_factors or 1) + (1 if n_factors > 1 else 0)   # per participant per pass
expected_total  = expected_groups × n_participants × min_expected_passes
depth = min(1, n_groups / expected_total)
```

### Blend

```
# Rank-all (default)
confidence = 0.35 × multi_pass + 0.45 × agreement_for_conf + 0.20 × depth

# Pick-one (exclusive_mode)
confidence = 0.30 × multi_pass + 0.50 × agreement_for_conf + 0.20 × depth
```

All components and outputs are in **\[0, 1\]**.

---

## 9. Completion (Participation bar)

```
completion = mean over participants of min(1, passes_i / min_expected_passes)
```

- `passes_i` = max `pass_index` among that participant’s groups  
- `min_expected_passes` project setting, default **2**, clamp **1–5**  
- Ceiling 1.0 — extra passes do not raise completion  

UI must display `asMetricPercent(completion)` (×100 when API sends fractions).

---

## 10. Dispersion

From per-participant overall rankings:

| Field | Meaning |
|-------|---------|
| `unique_leaders` | Distinct #1 option ids |
| `clustering_index` | Share of participants on the modal #1 |
| `dispersion_index` | Mean over options of (stdev of mean_rank) / (n_options−1), clamped \[0,1\] |
| `mean_rank_by_alternative` | id → average rank across participants |

---

## 11. Coherence (participant vs group)

Spearman ρ or Kendall τ between participant overall ranks and group overall ranks (setting `coherence_method`).

Stored as:

- `coherence_raw` ∈ \[−1, 1\]  
- `coherence` = `(raw + 1) / 2` ∈ \[0, 1\] for UI “align %”

---

## 12. Multi-pass averaging (important)

Within a channel, multiple `pass_index` rows are **mean-averaged** before scoring:

```
mean_rank_i = average of rank_i across passes
```

A leader can be a **compromise** of disagreeing passes (e.g. #3 then #2 beats #1 then #7).  
`pass_consistency` on by-factor rows is the multi-pass JS-agreement for that channel — low means the mean rank is unstable across repeats.

---

## 13. Report payload (contract)

`build_report` returns (key fields):

| Key | Content |
|-----|---------|
| `option_ranking` | Adjusted (factor-weighted) options; `score` ∈ \[0,1\] |
| `option_ranking_equal` | Equal factor weights |
| `factor_ranking` | Factors with `score`, `normalizedWeight`, conf/stab % |
| `factor_weights` | id → weight |
| `by_factor` | fid → option ranking under that factor |
| `metrics` | stability, stability_basis, confidence, multi_pass, factor_divergence, agreement, depth, completion, counts (fractions) |
| `dispersion` | see §9 |
| `participants[]` | `option_ranking`, `ranking` alias, `leader`, stability/confidence (0–1), coherence, counts |
| `pivot` | by_participant / by_factor / by_alternative rollups |
| `results.importance_adjusted` / `equal_weight` / `leader` / `criterion_weights` | Share-report compatibility |
| `total_observations` / `comparison_count` | Sort-internal pair counts (not pair-model evidence) |

Metrics at the API boundary are **0–1 fractions**. Clients convert with `asMetricPercent` / Results `pct()`.

---

## 14. What not to do

- Do **not** aggregate Results from `pairings` or legacy pair observations.  
- Do **not** emit rank-distance as `score` (e.g. 4.0 for five options).  
- Do **not** feed 0–1 metrics into labels that expect 0–100 without conversion.  
- Do **not** double-apply β when computing influence (`mass = w × n`, not `w × n^β`).  
- Do **not** use cross-factor option-list agreement as stability or multi-pass.  
- Do **not** treat high factor divergence as a quality failure.

---

## 15. Change control

When changing formulas:

1. Update this file and `src/utils/vote_ranking.py` together.  
2. Extend `src/tests/test_vote_ranking_probes.py` (scores ∈ \[0,1\], stability/confidence ranges, influence).  
3. Keep UI helpers in `client/utils/ranking.ts` aligned (`formatPercent`, `asMetricPercent`, `mapServerRanking`).  
4. Bump `settings.VERSION` on shippable changes.
