import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  formatRankCi,
  formatNullablePercent,
  formatExpectedRank,
  formatWeightCi,
  headlineOptionLabel,
  normalizeRankingMode,
  optionChanceCaption,
  polarizingCaption,
  insightMetricChips,
  mapServerRanking,
  personalRankingsFromSummary,
  metricLabel,
} from './ranking.ts'

test('formatRankCi rounds 1-based bounds', () => {
  assert.equal(formatRankCi([1.1, 3.4]), 'ranks 1–3')
  assert.equal(formatRankCi([2, 2]), 'rank 2')
  assert.equal(formatRankCi(null), null)
  assert.equal(formatRankCi([1]), null)
})

test('optionChanceCaption follows ranking mode', () => {
  const row = { p_best: 0.62, p_top_n: 0.81 }
  assert.equal(optionChanceCaption(row, 'find_best', 1), "62% chance it's #1")
  assert.equal(optionChanceCaption(row, 'find_top_3', 3), '81% chance in top 3')
  assert.equal(optionChanceCaption(row, 'find_top_half', 4), '81% chance in top 4')
  assert.equal(optionChanceCaption(row, 'rank_all', 6), null)
})

test('insight chips use expected pair agreement and do not show 0% as empty agreement', () => {
  const chips = insightMetricChips({
    ranking_mode: 'find_best',
    exclusive_mode: true,
    comparison_count: 12,
    top_n: 1,
    option_ranking: [{ id: 1 }, { id: 2 }],
    coherence: { expected_pair_agreement: 0.74 },
    posterior_stability: {
      same_winner_repeat_probability: 0.55,
      same_top_n_repeat_probability: 0.55,
    },
  })
  assert.deepEqual(chips.map(c => c.label), ['Agreement', 'Repeatability'])
  assert.equal(chips[0].display, '74%')
  assert.equal(chips[1].display, '55%')
  assert.match(chips[0].caption, /pair/)
})

test('insight chips treat missing agreement as not enough comparisons', () => {
  const chips = insightMetricChips({
    ranking_mode: 'rank_all',
    comparison_count: 0,
    coherence: { expected_pair_agreement: 0 },
    posterior_stability: {},
  })
  assert.equal(chips[0].display, '—')
  assert.equal(chips[0].caption, 'Not enough comparisons')
  assert.equal(chips[1].display, '—')
})

test('top-N mode uses same_top_n for Repeatability', () => {
  const chips = insightMetricChips({
    ranking_mode: 'find_top_3',
    comparison_count: 20,
    top_n: 3,
    option_ranking: [{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }],
    coherence: { expected_pair_agreement: 0.6 },
    posterior_stability: {
      same_winner_repeat_probability: 0.4,
      same_top_n_repeat_probability: 0.7,
    },
  })
  assert.equal(chips[1].display, '70%')
  // Stability removed — repeatability alone captures the posterior repeat probability
  assert.equal(chips.length, 2)
})

test('headline and polarizing copy', () => {
  assert.equal(headlineOptionLabel('find_best'), 'Recommended option')
  assert.equal(headlineOptionLabel('rank_all'), 'Top option')
  assert.equal(
    polarizingCaption({ title: 'Option A', expected_rank: 2.2, polarizing: true }),
    'Option A: consensus #2, highly polarizing',
  )
  assert.equal(polarizingCaption({ title: 'Calm', polarizing: false }), null)
})

test('mapServerRanking forwards posterior fields', () => {
  const mapped = mapServerRanking([
    {
      id: 9,
      title: 'Alpha',
      score: 0.71,
      mean_rank: 0.4,
      p_best: 0.66,
      p_top_n: 0.9,
      rank_ci95: [1, 2],
      expected_rank: 1.4,
      rank_sd: 0.45,
      polarizing: true,
      discrimination: 0.12,
      leverage: 0.4,
      weight_ci95: [0.2, 0.35],
      normalizedWeight: 0.28,
    },
  ])
  assert.ok(mapped)
  assert.equal(mapped[0].p_best, 0.66)
  assert.deepEqual(mapped[0].rank_ci95, [1, 2])
  assert.equal(mapped[0].polarizing, true)
  assert.equal(mapped[0].leverage, 0.4)
  assert.equal(mapped[0].rank_sd, 0.45)
  assert.equal(formatRankCi(mapped[0].rank_ci95), 'ranks 1–2')
  assert.equal(formatExpectedRank(mapped[0].expected_rank), '1.4')
  assert.equal(formatWeightCi(mapped[0].weight_ci95), '20%–35%')
  assert.equal(formatNullablePercent(null), '—')
  assert.equal(normalizeRankingMode('pick_one'), 'find_best')
})

test('personalRankingsFromSummary maps vote-view thank-you payload', () => {
  const mapped = personalRankingsFromSummary(
    {
      ranking_mode: 'rank_all',
      top_n: 2,
      confidence: 0.72,
      exclusive_mode: false,
      alternative_leaderboard: [
        { id: 1, title: 'Alpha', score: 0.8, rank_ci95: [1, 2], expected_rank: 1.2, rank_sd: 0.4, p_best: 0.7 },
        { id: 2, title: 'Beta', score: 0.2, rank_ci95: [1, 2], expected_rank: 1.8, rank_sd: 0.5 },
      ],
      factor_leaderboard: [
        { id: 10, title: 'Cost', weight: 0.62, weight_ci95: [0.4, 0.8], discrimination: 0.3, leverage: 0.5 },
        { id: 11, title: 'Quality', weight: 0.38, discrimination: 0.2, leverage: 0.4 },
      ],
    },
    { ranking_mode: 'find_best' },
  )
  assert.equal(mapped.options.length, 2)
  assert.equal(mapped.factors.length, 2)
  assert.equal(mapped.showFactors, true)
  assert.equal(mapped.rankingMode, 'find_best')
  assert.equal(mapped.topN, 2)
  assert.equal(mapped.confidence, 0.72)
  assert.equal(metricLabel(mapped.confidence ?? 0), 'Solid')
  assert.equal(formatRankCi(mapped.options[0].rank_ci95), 'ranks 1–2')
  assert.equal(mapped.options[0].rank_sd, 0.4)
  assert.equal(optionChanceCaption(mapped.options[0], mapped.rankingMode, mapped.topN), "70% chance it's #1")
  assert.equal(mapped.factors[0].weight, 0.62)
})

test('personalRankingsFromSummary hides factor pane for a single factor', () => {
  const mapped = personalRankingsFromSummary({
    ranking_mode: 'rank_all',
    alternative_leaderboard: [{ id: 1, title: 'Only', score: 1 }],
    factor_leaderboard: [{ id: 10, title: 'Overall', weight: 1 }],
  })
  assert.equal(mapped.showFactors, false)
  assert.equal(mapped.rankingMode, 'rank_all')
  assert.equal(optionChanceCaption(mapped.options[0], mapped.rankingMode, mapped.topN), null)
})
