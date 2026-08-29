# Implementation Specification: Adaptive Pairwise Ranking and Statistical Confidence Engine

## Objective

Implement a precision decision-support system based on repeated pairwise A/B comparisons.

The system must support:

* identification of the best option;
* identification and ranking of a top-N subset;
* complete ranking of all options;
* comparisons under individual decision factors;
* pairwise comparison of the factors themselves to estimate relative importance;
* multiple participants;
* multiple passes/groups by the same participant;
* participant-specific and population-level confidence;
* coherence/agreement statistics;
* repeatability/stability statistics;
* factor strength and decision-leverage statistics;
* complete propagation of factor and option uncertainty into the final multi-factor result.

The architecture is deliberately split:

**TypeScript client**

* chooses which pair to show next;
* uses only the available pair history for the participant and the question target;
* enforces all presentation constraints;
* does not duplicate a single option pair within a group or have the same option in two successive questions (unless too few options exist). The same applies when ranking factors amongst themselves..
* performs only lightweight, provisional calculations needed to choose a useful next pair;
* does NOT calculate or report authoritative statistical confidence.

**Python server**

* owns all authoritative statistical inference;
* calculates rankings, confidence, factor weights, participant agreement, stability, repeatability, model fit, and related analytics;
* produces the data used by dashboards, reports, result views, exports, and explanatory statistics.
* stores and databases question groups, and intermediate question groups, from participants with the result pairs, tentative ranking, and other data. This is analyzed in aggregate, from all groups, factors, and partipancts for the dashboard.

The Ford-Johnson algorithm itself is NOT used for any ranking or selection algorithm. Its worst-case comparison count is used to set the single group **question budget**.

---

# 1. Fundamental terminology

A **project/question** contains a set of options.

A **factor** is a criterion under which options may be compared, such as:

* Cost
* Customer Value
* Time to Implement
* Risk

A **group** or **pass** is one bounded sequence of pairwise questions for a participant.

Examples:

* Option comparisons under Cost, pass 1
* Option comparisons under Cost, pass 2
* Option comparisons under Customer Value
* Factor-importance comparisons

Each group has:

```typescript
type RankingTarget =
  | { mode: "winner" }
  | { mode: "top_n"; n: number }
  | { mode: "full" };
```

Historical comparisons from earlier passes are available for scheduling and server inference.

A pair may occur again in a subsequent pass, but **within one group the same unordered pair may appear only once**.

---

# 2. Question budget

For `n` alternatives, calculate the maximum number of questions from the Ford-Johnson / MergeInsertion worst-case count:

[
B(n)=
\sum_{i=1}^{n}
\left\lceil
\log_2(3i/4)
\right\rceil
]

TypeScript:

```typescript
export function fordJohnsonBudget(n: number): number {
  let total = 0;

  for (let i = 1; i <= n; i++) {
    total += Math.ceil(Math.log2((3 * i) / 4));
  }

  return total;
}
```

This defines the maximum question budget.

The adaptive scheduler spends that budget more intelligently than Ford-Johnson because human answers are noisy and should not be treated as mathematically infallible comparisons.

Unless product configuration says otherwise, use the entire available budget to maximize precision.

---

# 3. Important feasibility cases

The combination of:

1. no repeated pair within a group, and
2. no option appearing in consecutive questions

creates some unavoidable small-N edge cases.

Questions themselves are vertices in a graph whose adjacency means "the two pairs share no option."

### n = 2

One question is possible.

This is fine.

### n = 3

After asking `A/B`, neither `A/C` nor `B/C` can immediately follow because both reuse an option.

Therefore only **one consecutive pairwise question** is possible without some separator.

This also means the first-group requirement that every option be shown cannot be satisfied in a pure three-option group under the strict adjacency rule.

The application must therefore support one of:

* interleaving an unrelated question;
* inserting a qualifying neutral separator/break;
* explicitly configured relaxation of the adjacency rule for `n=3`.

Do not silently violate the constraint.

### n = 4

After:

```text
A / B
C / D
```

the only pair disjoint from `C/D` is `A/B`, which is already used.

Therefore a strict uninterrupted four-option group can contain at most two questions, considerably fewer than the Ford-Johnson budget of five.

Again use an interleaving/separator mechanism if the full budget is required.

### n >= 5

The pair space is sufficiently rich to support long sequences of distinct pairs with disjoint consecutive questions.

Nevertheless, the client scheduler must perform feasibility/look-ahead checking rather than assuming every locally attractive pair leaves a valid future sequence.

These cases require explicit automated tests.

---

# 4. Client responsibilities

The TypeScript client owns only question sequencing.

It must enforce:

### Hard constraints

Within the current group:

1. An unordered pair may be shown only once.
2. Neither item from the immediately preceding question may appear in the next question.
3. In the **first pass only**, every option must appear at least once.
4. In subsequent passes there is no minimum-exposure requirement.
5. Do not exceed the Ford-Johnson question budget.
6. An Undo must restore the previous scheduler state and normally reproduce the same next pair.
7. Pair orientation left/right should be balanced independently from pair selection.

Historical comparisons from earlier passes are **not** considered duplicates for rule #1.

---

# 5. Client scheduler should be adaptive but lightweight

The client does not need authoritative Bayesian inference.

However, random pairing throws away much of the benefit of adaptive questioning.

Use a lightweight provisional Bradley-Terry-style score derived only from:

* earlier pair history for this participant;
* current-group answers;
* target mode;
* current-group exposure;
* current-group used pairs.

The resulting scores exist only to choose questions.

They must never be presented as statistical confidence.

---

# 6. Provisional client pair model

Maintain provisional option strengths:

[
s_i
]

and estimate:

[
p_{ij}
======

# P(i>j)

\sigma(s_i-s_j)
]

where:

[
\sigma(x)=\frac{1}{1+e^{-x}}
]

Use deterministic regularized batch optimization or a small fixed number of gradient iterations.

A simple implementation is sufficient.

For example:

```typescript
interface PairResult {
  itemA: string;
  itemB: string;
  winner: string;
  passIndex: number;
}
```

Fit provisional scores from historical plus current responses.

Regularize toward zero so sparse data cannot create extreme scores.

Always recenter scores:

```text
mean(score[]) = 0
```

after optimization.

The exact client values are not authoritative; stability, determinism, and sensible pair selection matter more than high-precision estimation here.

---

# 7. Information value of a candidate pair

A useful lightweight approximation to the Fisher information in one Bradley-Terry observation is:

[
I_{ij}=4p_{ij}(1-p_{ij})
]

This ranges approximately:

```text
0     very predictable comparison
1     maximally uncertain 50/50 comparison
```

Do **not** simply select the pair nearest 50/50.

Pair informativeness must be weighted according to the ranking objective.

---

# 8. Goal-dependent pair selection

## Winner mode

Questions should increasingly distinguish plausible leaders.

Give high weight to pairs involving:

* current provisional #1;
* close challengers;
* alternatives with scores close to the leader.

Avoid wasting late questions distinguishing two options that are provisionally far below the leaders.

A useful smooth relevance function is:

[
T_i=\exp(-(rank_i-1)/\tau)
]

and:

[
T_{ij}=(T_i+T_j)/2
]

with an additional bonus when one option is the current leader.

---

# 9. Top-N mode

This is especially important.

Most information should eventually concentrate near the boundary between:

```text
rank N
rank N+1
```

Let:

```text
boundaryScore =
(score[N] + score[N+1]) / 2
```

and calculate:

[
D_i =
\exp(-|s_i-boundaryScore|/\tau_s)
]

Then:

[
T_{ij}=(D_i+D_j)/2
]

Add a substantial bonus when one provisional option is inside the top N and the other is outside:

```typescript
const straddlesBoundary =
  (rankA <= topN) !== (rankB <= topN);
```

For a ranked top-N result, do not ignore internal ordering.

A reasonable acquisition objective is conceptually:

```text
65% confidence in membership boundary
35% ordering within the top-N set
```

This can be configurable later.

---

# 10. Full-ranking mode

For a complete ranking, concentrate questions on nearby provisional ranks.

A reasonable target weight is:

[
T_{ij}
======

\exp(-(|rank_i-rank_j|-1)/\tau_r)
]

Thus:

```text
#3 vs #4 -> very useful
#3 vs #15 -> normally much less useful
```

unless the latter also serves graph connectivity or resolves contradictory historical evidence.

---

# 11. Graph connectivity is essential

Treat options as vertices and comparisons as edges.

A ranking graph that consists only of:

```text
A > B
C > D
E > F
```

does not provide enough evidence to place the three pairs relative to one another.

Therefore the scheduler must also consider graph connectivity.

After mandatory first-pass exposure is complete, strongly prioritize candidate pairs that connect previously disconnected components.

For example:

```text
A-B
C-D
E-F
A-C
B-E
```

rapidly turns separate components into one comparison network.

Use historical plus current comparisons when determining whether the participant's comparison graph is already connected.

A candidate edge connecting two currently disconnected components should receive a large acquisition bonus.

---

# 12. First-pass exposure strategy

Only the first pass requires every option to appear.

Do not merely attach a small scoring bonus to unseen items.

Make coverage a hard condition.

A practical strategy is:

### While two or more options remain unseen

Prefer pairs consisting of two unseen options, subject to constraints.

This naturally produces:

```text
A/B
C/D
E/F
...
```

### If exactly one option remains unseen

Pair it with the highest-value legal previously seen option that:

* was not in the immediately preceding question;
* has not already been paired with the unseen option.

For odd `n >= 5`, this works naturally.

Once all options have appeared, switch fully to the adaptive objective.

---

# 13. Later passes

Subsequent passes have no minimum exposure rule.

This is important.

Do **not** force every option to appear again.

Use the entire comparison budget where it produces the most information.

For a top-three question, for example, later passes may legitimately concentrate most questions around options provisionally ranked approximately 1-5.

Historical repeated pairs are permitted across passes and are statistically valuable.

However, use diminishing returns so the scheduler does not repeatedly ask exactly the same pairs pass after pass without reason.

---

# 14. Historical repeated-pair information

For candidate pair `(i,j)` calculate:

```text
historicalCount(i,j)
historicalWinsI
historicalWinsJ
```

Consistent repeated answers increase confidence.

Inconsistent answers indicate that the pair may represent a genuine close call or lower repeatability.

A useful historical inconsistency measure is:

[
C_{ij}=4q_{ij}(1-q_{ij})
]

where `q` is the historical proportion favoring `i`.

Do not automatically avoid inconsistent pairs.

For important top-N boundary comparisons, disagreement may make another observation particularly valuable.

Apply a modest diminishing-return factor such as:

[
R_{ij}
======

\frac{1}{\sqrt{1+\alpha,historicalCount_{ij}}}
]

while also allowing target importance and historical inconsistency to overcome that penalty.

---

# 15. Combined client acquisition score

A reasonable initial acquisition function is:

[
A_{ij}
======

I_{ij}
\times
T_{ij}
\times
R_{ij}
\times
E_{ij}
\times
G_{ij}
]

where:

* (I) = Bradley-Terry uncertainty;
* (T) = target relevance;
* (R) = historical diminishing-return adjustment;
* (E) = exposure/balance adjustment;
* (G) = graph-connectivity adjustment.

Then add explicit bonuses for:

* top-N boundary straddling;
* connecting disconnected graph components;
* resolving historically inconsistent high-value comparisons.

Hard constraints must always be applied **before** this score.

Do not make illegal pairs merely receive low scores.

Remove them entirely.

---

# 16. Future-feasibility checking

Before accepting the highest-scoring candidate, verify that it does not make the remaining schedule impossible.

At minimum check:

```text
candidate pair unused
candidate pair disjoint from previous pair
remaining legal pair exists if more questions remain
first-pass unseen items can still all be covered
```

Implement short backtracking/look-ahead.

For small item sets, search all the way to the end of the remaining group.

For larger sets, a look-ahead of approximately 3 questions plus coverage feasibility is sufficient in normal cases.

Conceptually:

```typescript
function selectNextPair(state: GroupState): Pair {
  const candidates = enumerateLegalPairs(state);

  const ranked = candidates
    .filter(pair => remainsFeasibleAfter(state, pair))
    .map(pair => ({
      pair,
      score: acquisitionScore(state, pair),
    }))
    .sort(stableDescendingScore);

  if (!ranked.length) {
    throw new PairScheduleConstraintError(...);
  }

  return ranked[0].pair;
}
```

---

# 17. Determinism and Undo

The scheduler should be deterministic for a given state.

An Undo should:

1. delete the most recent response;
2. remove its dwell time;
3. make that pair available again;
4. restore exposure counts;
5. restore the previous last pair;
6. refit provisional client scores;
7. run pair selection again.

The same prior state should normally generate the same pair.

If stochastic tie-breaking is desired, derive the random seed from a stable hash of:

```text
project ID
participant ID
group ID
pass number
target
sorted active comparison IDs
```

Therefore restoring the state also restores the random sequence.

Do not use a continuously advancing global RNG.

---

# 18. Left/right orientation

Pair selection and screen orientation are separate operations.

After selecting `(A,B)`, choose whether the user sees:

```text
A | B
```

or:

```text
B | A
```

Prefer the orientation that best balances historical left/right exposures for each item.

Use deterministic seeded randomization when both orientations are equally balanced.

Store the actual orientation.

The server should test for systematic left/right selection bias.

---

# 19. Comparison event schema

Preserve raw response events.

Do not reduce history to aggregate win counts.

Recommended structure:

```typescript
interface PairComparisonEvent {
  id: string;

  projectId: string;
  participantId: string;

  groupId: string;
  passIndex: number;

  groupType:
    | "option_comparison"
    | "factor_importance";

  factorId?: string;

  itemAId: string;
  itemBId: string;
  winnerId: string;

  leftItemId: string;
  rightItemId: string;

  sequenceNumber: number;

  shownAt: string;
  answeredAt: string;
  dwellMs: number;

  rankingTarget:
    | "winner"
    | "top_n"
    | "full";

  topN?: number;
}
```

An Undo should normally remove/invalidate the active response rather than silently rewriting aggregate statistics.

If audit history is required, retain an immutable event and mark it superseded/undone.

The statistical engine must use only active answers.

---

# 20. Server statistical architecture

The Python service is authoritative.

Use a hierarchical Bayesian Bradley-Terry / random-utility model as the principal inferential model.

A practical stack is:

```text
Python
NumPy
SciPy
Pandas
PyMC or NumPyro
ArviZ or equivalent posterior diagnostics
```

Keep the model interface independent of the chosen sampler.

For frequently refreshed dashboard values, a Laplace or variational approximation can optionally provide provisional results.

Final/report-quality values should use the authoritative posterior model, preferably full posterior sampling when data volume permits.

Cache statistics against an exact comparison-data version so repeated result requests do not unnecessarily rerun inference.

---

# 21. Basic factor-specific option model

For option `i` under factor `f`, let:

[
\mu_{fi}
]

represent population-level latent preference.

For participant `p`, include participant deviation:

[
u_{pfi}
]

so:

[
\theta_{pfi}
============

\mu_{fi}+u_{pfi}.
]

Comparison:

[
\Delta_{pfij}
=============

\theta_{pfi}-\theta_{pfj}.
]

Then:

[
P_p(i>j)
========

\sigma(\Delta_{pfij})
]

in the simplest model.

Apply sum-to-zero constraints or equivalent centering for identifiability.

Use hierarchical shrinkage on participant deviations so participants with few observations are pulled appropriately toward the population estimate.

---

# 22. Separate preference heterogeneity from response unreliability

A participant disagreeing with everyone else is not necessarily unreliable.

They may have a genuinely different preference.

Therefore participant-specific option deviations and response noise must be modeled separately.

Recommended robust model:

[
P_p(i>j)
========

(1-\lambda_p)
\sigma(
\kappa_p\Delta_{pfij}
+
\beta_L L
)
+
\lambda_p/2
]

where:

* (\lambda_p) = participant lapse/random-response probability;
* (\kappa_p) = participant consistency/discrimination parameter;
* (\beta_L) = optional population left/right bias;
* (L) indicates orientation.

Use hierarchical priors.

Do not estimate an excessive number of participant-specific noise parameters when a participant has too little data.

Shrink heavily toward population values.

This model separates:

```text
"I consistently prefer something different"
```

from:

```text
"My individual answers are difficult to predict."
```

That distinction is critical.

---

# 23. Pass-to-pass preference drift

Historical passes should normally retain full statistical value.

Do not automatically decay old observations.

If the application eventually accumulates evidence that preferences change over time, add a pass/time random effect such as:

[
d_{pfi,t}
]

with shrinkage toward zero.

Only introduce temporal discounting or drift if empirical validation shows it improves prediction.

---

# 24. Posterior rank calculation

For every posterior draw:

```text
theta(sample, item)
```

rank all alternatives.

For item `i`, calculate the empirical posterior distribution:

[
P(R_i=r).
]

This distribution is the foundation of confidence reporting.

For each item return at least:

### Consensus rank

Rank from posterior mean or median utility.

### Expected rank

[
E[R_i]
]

### Median rank

Useful when the distribution is asymmetric.

### Exact-rank confidence

[
P(R_i=\hat R_i)
]

### Winner probability

[
P(R_i=1)
]

### Top-N probability

[
P(R_i\le N)
]

### Rank credible interval

For example:

```text
95% rank interval = 2-5
```

### Rank entropy

[
H(R_i)
======

-\sum_r P(R_i=r)\log P(R_i=r)
]

Normalize if desired:

[
H^*_i=H(R_i)/\log(n)
]

and expose confidence as:

[
1-H^*_i.
]

Keep raw posterior statistics available even if UI converts them into friendlier labels.

---

# 25. Pairwise probability matrix

Return the posterior probability:

[
P(i>j)
]

for every pair.

This matrix supports:

* dominance displays;
* explanation of close ranks;
* sensitivity reports;
* confidence diagnostics.

For every option calculate an expected pairwise-win score:

[
Q_i
===

\frac{1}{n-1}
\sum_{j\ne i}
P(i>j).
]

This ranges from zero to one and is particularly useful for multi-factor aggregation because it places every factor-specific option evaluation on a common bounded scale.

---

# 26. Winner-level confidence

For winner-target questions, report:

[
P(\text{displayed winner is truly #1}).
]

Also return:

```text
P(#1)
P(#2)
P(#3)
...
```

for leading candidates so a report can distinguish:

```text
A is overwhelmingly likely to win
```

from:

```text
A is currently ranked first, but A and B are effectively unresolved.
```

---

# 27. Top-N confidence

For every item calculate:

[
P(R_i\le N).
]

For the displayed top-N set also calculate:

### Exact set probability

Probability that the precise displayed membership set is the true posterior top-N set.

### Expected overlap

Expected number of displayed top-N options retained in a posterior sample.

### Expected Jaccard similarity

[
J(A,B)=
\frac{|A\cap B|}{|A\cup B|}.
]

Exact-set probability can become low when many options are close, so do not use it alone.

A top-N result may be very useful even when exact ordering within the top N remains uncertain.

---

# 28. Full-ranking confidence

Do not report only:

```text
probability that the entire permutation is exactly correct
```

because it becomes tiny for moderately large `n`.

Also calculate:

* posterior expected Kendall correlation with displayed ranking;
* expected number of reversed option pairs;
* expected absolute rank error;
* normalized rank entropy;
* per-option credible rank ranges.

A useful overall stability interpretation is:

```text
Expected percentage of pairwise ordering relationships
that remain unchanged across posterior draws.
```

---

# 29. Multi-participant population model

The hierarchical model should produce both:

### Consensus/population ranking

Using population latent option values.

### Participant-specific rankings

Using:

[
\mu_{fi}+u_{pfi}.
]

Do not average raw participant ranks as the main estimator.

Infer consensus from the pairwise evidence.

Participant-specific posterior rankings are then useful for coherence and heterogeneity measurements.

---

# 30. Participant coherence

Coherence means alignment between participants, not correctness.

Use several complementary statistics.

## Pairwise directional coherence

For pair `(i,j)` let:

[
\bar p_{ij}
===========

P(\text{random population participant chooses }i).
]

Define:

[
C_{ij}
======

|2\bar p_{ij}-1|.
]

Interpretation:

```text
0.0 = population evenly divided
1.0 = population completely aligned
```

Average this over relevant pairs.

For target-specific reporting, additionally weight pairs near the winner/top-N boundary.

---

# 31. Expected participant-pair agreement

For a comparison with population choice probability `p`:

[
A_{ij}
======

p^2+(1-p)^2.
]

This is the probability that two randomly selected comparable participants give the same answer.

Average across pairs.

Report as something similar to:

```text
Expected participant agreement: 81%
```

This is intuitive and useful.

---

# 32. Participant ranking agreement

Using posterior participant rankings calculate:

* participant-to-consensus Kendall correlation;
* average participant-to-participant Kendall correlation;
* top-N membership Jaccard similarity;
* winner agreement frequency.

Calculate uncertainty intervals for these statistics from posterior samples.

If sufficient participants have actually evaluated identical pairs, optionally provide a chance-corrected shared-pair agreement statistic as a secondary diagnostic.

Do not make kappa-like statistics primary when pair overlap is sparse.

---

# 33. Per-option participant coherence

For each option calculate across participants:

[
SD_p(R_{pi})
]

and:

[
E_p|R_{pi}-R_i^{consensus}|.
]

A normalized option coherence score can be:

[
C_i
===

1-
\frac{
E_p|R_{pi}-R_i^{consensus}|
}{
n-1
}.
]

Also return:

* participant rank distribution;
* population top-N probability;
* proportion of participants for whom item is top-N;
* pairwise disagreement centered on this option.

This allows results such as:

```text
Option A: consensus rank #2, highly polarizing

Option B: consensus rank #3, broadly placed between #2 and #4
```

---

# 34. Individual participant repeatability

For an individual predicted pair choice probability:

[
p=P(i>j)
]

the probability of answering the same way on two independent repetitions is:

[
p^2+(1-p)^2.
]

Use the participant-specific posterior.

Calculate:

### Overall participant repeatability

Across relevant pairs.

### Decision-region repeatability

Weighted toward the current winner/top-N boundary.

### Empirical pass-to-pass repeatability

When identical pairs have actually occurred across passes:

```text
same answer / repeated pair observations
```

Use empirical repeated comparisons to validate and calibrate model-predicted repeatability.

---

# 35. Participant basket stability

Answer:

> If another comparable set of participants performed the process, how similar would the result probably be?

Use hierarchical posterior predictive simulation and participant bootstrap.

Calculate:

* probability of same winner;
* probability of same top-N set;
* expected top-N Jaccard similarity;
* expected Kendall correlation;
* expected absolute rank movement;
* distribution of each item's rank.

Separate:

### Response repeatability

Same underlying participants responding again.

### Sample robustness

A new basket of comparable participants.

These are different statistics and should not be merged.

---

# 36. Leave-one-participant-out influence

For precision reporting, calculate how sensitive results are to individual participants.

Useful outputs:

```text
largest winner-probability change after excluding one participant
largest top-N membership change
largest option-rank change
```

Flag results dominated by a single participant.

For larger participant counts this can be approximated from posterior influence diagnostics rather than refitting everything literally.

---

# 37. Dwell-time handling

Always retain dwell time.

Do **not** initially assign higher statistical weight merely because an answer took longer.

Likewise, do not automatically down-weight quick answers.

A quick answer may represent:

```text
obvious preference
```

or:

```text
careless clicking
```

A slow answer may represent:

```text
careful thought
```

or:

```text
genuine ambiguity
```

Initially use dwell time diagnostically.

---

# 38. Dwell-time model

After sufficient data exists, fit something like:

[
\log(T)
\sim
N(
\alpha_p
+
\alpha_f
+
\beta_1 Difficulty
+
\beta_2 QuestionPosition,
\sigma_T
)
]

where comparison difficulty can derive from:

[
4p(1-p)
]

or equivalent latent score separation.

This allows identification of responses that are unusually fast relative to both:

* participant baseline;
* expected difficulty.

Also evaluate fatigue through question position.

Only allow dwell information to modify response reliability if cross-validation demonstrates improved prediction of repeated answers.

---

# 39. Transitivity and cycles

Bradley-Terry assumes an underlying transitive latent order.

Human preferences may contain:

[
A>B,\quad
B>C,\quad
C>A.
]

Track:

* observed three-cycle frequency;
* posterior expected cycle frequency;
* excess cyclic inconsistency;
* residual pair effects;
* posterior predictive error.

Do not automatically interpret every cycle as low-quality data.

Persistent cycles may represent genuine context-sensitive or multidimensional preference.

The initial authoritative model should remain hierarchical Bradley-Terry.

Add pair-specific/intransitive extensions only where diagnostics demonstrate that they materially improve predictive accuracy.

---

# 40. Model quality statistics

The server should expose diagnostic/QA statistics even if most remain hidden from ordinary users.

Include:

* posterior predictive log loss;
* Brier score;
* calibration by predicted probability;
* posterior predictive checks;
* graph connectivity;
* comparison coverage;
* effective participant sample;
* left/right bias;
* question-position/fatigue effect;
* lapse/reliability distribution;
* cycle/intransitivity diagnostics;
* posterior sampler convergence diagnostics;
* effective sample size;
* sensitivity to modeling assumptions.

Use information criteria or out-of-sample validation when comparing alternate models.

Do not select models purely because they produce narrower confidence intervals.

---

# 41. Factor-specific option analysis

Run the same option-ranking model independently/jointly for every factor.

For each `(factor, option)` calculate:

```text
factor-specific consensus rank
expected rank
exact-rank probability
winner probability
top-N probability
rank credible interval
rank entropy
expected pairwise-win score
participant coherence
repeatability
```

This creates detailed support for statements such as:

```text
Option A is clearly strongest on Customer Value,
but its Cost ranking is highly uncertain.
```

---

# 42. Factor importance comparisons

Factors themselves are compared as alternatives.

Let:

[
\phi_f
]

be latent factor importance.

Use the same hierarchical pairwise model:

[
P(f>g)
======

\sigma(\phi_f-\phi_g)
]

with participant-specific deviations where appropriate.

Convert posterior factor utilities into relative weights:

[
w_f
===

\frac{\exp(\phi_f)}
{\sum_g\exp(\phi_g)}.
]

Calculate this separately for every posterior draw.

For each factor return:

* expected weight;
* median weight;
* 95% credible weight interval;
* expected importance rank;
* exact importance-rank confidence;
* probability factor is most important;
* factor-rank entropy;
* participant coherence on factor importance;
* participant-specific weight distribution.

Treat the resulting weights as model-derived relative decision weights.

Do not describe pairwise factor comparisons as measuring literal ratio-scale cardinal importance without qualification.

---

# 43. Common-scale multi-factor option scores

Do not directly add raw Bradley-Terry latent values from separately estimated factors unless a common latent scale has been explicitly identified.

Instead derive a bounded factor-specific strength:

[
Q_{fi}
======

\frac{1}{n-1}
\sum_{j\ne i}
P(i>j\mid f).
]

Thus:

```text
0.0 = loses against essentially everything
0.5 = middle of the group
1.0 = dominates essentially everything
```

Calculate (Q_{fi}) for every posterior draw.

Then combine factors:

[
U_i
===

\sum_f
w_fQ_{fi}.
]

Rank `U_i` separately for every posterior draw.

This automatically propagates uncertainty in:

* option comparisons;
* factor rankings;
* factor weights;
* participant heterogeneity.

Use these posterior overall rankings for the final multi-factor confidence values.

---

# 44. Factor strength versus factor importance

These are not equivalent.

A factor can be extremely important but fail to distinguish between options.

Calculate at least three separate concepts.

## Factor importance

[
I_f=E[w_f].
]

## Factor discrimination

For example:

[
D_f
===

SD_i(Q_{fi})
]

or an equivalent range/dispersion metric.

This measures how strongly the factor differentiates the current alternatives.

## Factor decision leverage

[
L_f=w_fD_f.
]

Normalize:

[
L_f^*
=====

\frac{L_f}{\sum_gL_g}.
]

This supports a much better dashboard:

| Factor         | Importance | Differentiation | Decision leverage |
| -------------- | ---------: | --------------: | ----------------: |
| Cost           |        28% |            High |               37% |
| Security       |        35% |             Low |               12% |
| Time           |        22% |          Medium |               26% |
| Customer Value |        15% |       Very High |               25% |

---

# 45. Factor-level decisiveness

Also calculate factor pairwise entropy:

[
H_f
===

\operatorname{mean}_{i<j}
h(P(i>j\mid f))
]

where:

[
h(p)
====

-p\log p-(1-p)\log(1-p).
]

Low entropy means the factor produces relatively decisive distinctions.

High entropy means alternatives are difficult to distinguish under that factor.

Do not confuse this with factor importance.

---

# 46. Factor contribution to an individual option

For an option `i`, calculate posterior contribution:

[
Contribution_{fi}
=================

w_fQ_{fi}.
]

Also calculate centered contribution if a more explanatory visualization is desired:

[
w_f(Q_{fi}-0.5).
]

This can explain:

```text
Option A's advantage comes primarily from
Customer Value and Time, partly offset by Cost.
```

---

# 47. Factor contribution to uncertainty

For each factor estimate how much uncertainty in that factor changes:

* winner identity;
* top-N membership;
* overall rank.

Use posterior sensitivity simulation.

Useful measures include:

```text
probability winner changes if factor is omitted
expected rank change if factor is omitted
change in top-N membership probability
reduction in overall rank variance if factor uncertainty is fixed
```

For high-value reports, use Monte Carlo variance decomposition or pick/freeze sensitivity analysis.

Avoid causal language.

These are decision-model sensitivity statistics.

---

# 48. Recommended server result structure

Conceptually return:

```python
{
    "group": {
        "target": ...,
        "question_budget": ...,
        "questions_answered": ...,
        "graph_connected": ...,
        "coverage": ...,
        "model_fit": ...,
    },

    "options": [
        {
            "option_id": ...,
            "rank": ...,
            "expected_rank": ...,
            "median_rank": ...,
            "rank_ci95": [..., ...],
            "p_exact_rank": ...,
            "p_best": ...,
            "p_top_n": ...,
            "rank_entropy": ...,
            "pairwise_win_strength": ...,
            "participant_rank_sd": ...,
            "participant_coherence": ...,
            "repeatability": ...,
        }
    ],

    "coherence": {
        "directional": ...,
        "expected_pair_agreement": ...,
        "participant_consensus_kendall": ...,
        "top_n_jaccard": ...,
        "cycle_rate": ...,
    },

    "stability": {
        "same_winner_repeat_probability": ...,
        "same_top_n_repeat_probability": ...,
        "basket_same_winner_probability": ...,
        "basket_top_n_jaccard": ...,
        "basket_kendall": ...,
        "max_single_participant_influence": ...,
    },

    "factors": [...],

    "overall_multifactor": {...},

    "diagnostics": {...}
}
```

Use API-friendly names but preserve underlying posterior distributions or quantiles server-side.

---

# 49. Dashboard presentation

Avoid reducing everything to one generic "confidence score."

At minimum keep these concepts distinct:

### Ranking Confidence

How certain are the actual ranks?

### Participant Coherence

How much do different participants agree?

### Repeatability

How likely is the same participant to respond similarly again?

### Basket Stability

How likely would a comparable new group of participants produce the same result?

### Factor Confidence

How certain are factor importance and factor-specific option rankings?

### Decision Leverage

Which factors actually determine the outcome?

### Model Quality

Does the observed comparison data behave reasonably under the statistical model?

The UI may summarize these into badges or percentages, but the underlying metrics must remain separate.

---

# 50. Do not use these shortcuts

Do **not** make any of the following the authoritative analysis:

```text
raw win percentage
Borda score alone
Copeland score alone
Elo rating alone
average participant rank
Ford-Johnson decision tree
simple majority vote
raw dwell-time weighting
```

These may be useful diagnostics or client heuristics but lose important uncertainty information.

---

# 51. Python posterior aggregation pattern

The implementation should ultimately operate on posterior samples.

For example:

```python
import numpy as np


def posterior_ranks(score_samples: np.ndarray) -> np.ndarray:
    """
    score_samples:
        shape [samples, items]

    Returns:
        shape [samples, items]
        rank 1 = best
    """
    order = np.argsort(-score_samples, axis=1)

    ranks = np.empty_like(order)

    rows = np.arange(score_samples.shape[0])[:, None]
    ranks[rows, order] = np.arange(
        1,
        score_samples.shape[1] + 1
    )

    return ranks


def rank_summary(score_samples, top_n):
    ranks = posterior_ranks(score_samples)

    mean_scores = score_samples.mean(axis=0)
    final_order = np.argsort(-mean_scores)

    assigned = np.empty(score_samples.shape[1], dtype=int)
    assigned[final_order] = np.arange(
        1,
        score_samples.shape[1] + 1
    )

    result = []

    for i in range(score_samples.shape[1]):
        ri = ranks[:, i]

        exact = np.mean(ri == assigned[i])

        result.append({
            "item": i,
            "rank": int(assigned[i]),
            "expected_rank": float(ri.mean()),
            "median_rank": float(np.median(ri)),
            "p_exact_rank": float(exact),
            "p_best": float(np.mean(ri == 1)),
            "p_top_n": float(np.mean(ri <= top_n)),
            "rank_ci95": [
                float(np.quantile(ri, .025)),
                float(np.quantile(ri, .975)),
            ],
        })

    return result
```

The hierarchical model should feed posterior samples into these generic aggregation functions.

---

# 52. Multi-factor posterior combination pattern

For posterior factor weights:

```python
def softmax(x, axis=-1):
    x = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)
```

Suppose:

```text
factor_latent:
    [samples, factors]

factor_option_win_strength:
    [samples, factors, options]
```

Then:

```python
weights = softmax(factor_latent, axis=1)

overall = np.einsum(
    "sf,sfo->so",
    weights,
    factor_option_win_strength,
)
```

`overall` is:

```text
[samples, options]
```

and goes directly through the same posterior ranking/statistics functions.

This posterior-sample-first architecture should be used consistently throughout the server.

---

# 53. Validation framework

Statistical quality must be validated empirically.

Historical repeated passes provide unusually valuable validation data.

Measure whether:

### Predicted pair probabilities are calibrated

Among responses predicted at approximately 70%, roughly 70% should favor the predicted option.

### Predicted repeatability is calibrated

Pairs predicted to repeat 85% of the time should actually repeat approximately 85% across passes.

### Rank confidence is calibrated

High-confidence ranks should move less frequently in later passes.

### Top-N confidence is calibrated

Options with 90% predicted top-N probability should remain inside the top N at approximately that rate under subsequent evidence.

### Dwell-time modeling improves prediction

Do not use it as a reliability modifier unless it improves held-out prediction.

### Participant reliability parameters predict future behavior

Do not merely fit historical noise.

---

# 54. Simulation testing

Build a substantial synthetic-data test suite.

Generate artificial participants from known latent utility models and test whether the system recovers:

* known winners;
* known top-N groups;
* full rankings;
* known factor weights;
* heterogeneous participant clusters;
* unreliable participants;
* close alternatives;
* obvious alternatives;
* deliberately cyclic data;
* left/right bias;
* high and low repeatability;
* preference drift;
* sparse data;
* disconnected comparison histories.

Also simulate the actual TypeScript pair scheduler.

Compare its performance with:

```text
random legal pair selection
fixed tournament pairing
ordinary merge sort comparisons
Ford-Johnson comparison sequence
uniform pair sampling
```

Measure after the identical Ford-Johnson question budget:

* winner accuracy;
* top-N accuracy;
* Kendall ranking correlation;
* average rank error;
* posterior entropy;
* calibration.

This simulation suite is one of the most important pieces of engineering in a precision decision-support product.

---

# 55. Scheduler acceptance tests

Include deterministic tests for at least:

### Constraints

```text
no duplicate unordered pair in one group
no option appears in consecutive questions
first pass presents every option
later passes do not require every option
question count never exceeds budget
historical pair can appear once in a new pass
```

### Undo

```text
answer question
undo
same state restored
same next pair selected
```

### n = 2

One valid question.

### n = 3

Strict adjacency constraints detected as incompatible with first-pass coverage without separator/interleaving.

### n = 4

Two-question uninterrupted maximum detected.

### n = 5+

Scheduler successfully uses the configured budget while respecting constraints.

### Target behavior

Winner mode increasingly emphasizes plausible winners.

Top-N mode increasingly emphasizes the N/N+1 boundary.

Full mode increasingly emphasizes uncertain nearby ranks.

### Connectivity

A previously disconnected comparison graph receives strong preference for bridging comparisons.

---

# 56. Statistical acceptance tests

Given synthetic known utilities:

```text
strong winner -> high winner probability
tied leaders -> appropriately broad uncertainty
clear top 3 -> high top-3 membership confidence
uncertain #3/#4 -> high boundary uncertainty
```

Given homogeneous participants:

```text
high coherence
low participant rank dispersion
```

Given intentionally polarized participants:

```text
consensus may be moderate
participant heterogeneity must be high
participants must NOT merely be labeled unreliable
```

Given random responders:

```text
repeatability approaches chance
lapse/noise estimate increases
```

Given repeated passes:

```text
predicted and empirical repeatability are comparable
```

Given a highly important factor that barely differentiates options:

```text
high importance
low discrimination
low-to-moderate decision leverage
```

Given a moderately important factor that strongly separates candidates:

```text
moderate importance
high discrimination
potentially high decision leverage
```

---

# 57. Architectural rule

Implement **one generic pairwise-ranking statistical engine**.

Do not build unrelated statistical implementations for:

```text
single-factor option ranking
factor importance
multi-participant ranking
overall decision ranking
```

They should share common components:

```text
comparison likelihood
participant hierarchy
reliability model
posterior sampling
rank summarization
coherence analysis
repeatability analysis
stability simulation
```

Factor weighting is simply another pairwise-ranking problem whose latent result is transformed into normalized weights.

Multi-factor decision ranking is a posterior aggregation layer over factor-specific pairwise results.

---

# 58. Architectural rule for the client

Likewise implement one generic TypeScript scheduler:

```typescript
selectNextPair({
    items,
    currentGroupHistory,
    previousGroupHistory,
    target,
    passIndex,
    questionBudget,
    lastPair,
})
```

It should work identically for:

* option comparisons;
* factor comparisons.

Only the identities of the objects change.

The scheduler's provisional Bradley-Terry calculation is solely an **acquisition heuristic**.

The Python server remains authoritative for all displayed statistical conclusions.

---

# 59. Final design principle

Treat the application as an **adaptive statistical measurement system**, not as a sorting algorithm.

Ford-Johnson provides an excellent disciplined comparison budget.

The client should spend that budget on the legal comparisons expected to be most informative for the requested decision target.

The Python server should then treat all observed answers as noisy evidence and calculate complete posterior distributions rather than pretending that an individual comparison establishes an incontrovertible ordering.

The resulting system should be able to distinguish, quantitatively:

```text
what appears to be best
how certain that conclusion is
whether exact rank is known
whether top-N membership is known
whether participants agree
whether individual participants are internally repeatable
whether another participant basket would reproduce the result
which factors are important
which factors actually distinguish the alternatives
which factors drive the final decision
where remaining uncertainty originates
whether the statistical model fits the observed behavior
```

That separation between **adaptive question acquisition on the client** and **authoritative probabilistic inference on the server** should remain a core architectural constraint throughout the implementation.
