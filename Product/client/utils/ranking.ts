/**
 * Display helpers and light client settings for ranked-group Results.
 * Pairwise Bayesian ranking has been removed — all Results math lives on the server
 * (src/utils/vote_ranking.py). See algos.md.
 */

export type ParticipantInfluenceMode = 'comparisons' | 'balanced' | 'participants_normalized'

export const PARTICIPANT_INFLUENCE_MODES: ParticipantInfluenceMode[] = [
  'comparisons',
  'balanced',
  'participants_normalized',
]

export const PARTICIPANT_INFLUENCE_BETA: Record<ParticipantInfluenceMode, number> = {
  comparisons: 1,
  balanced: 0.5,
  participants_normalized: 0.1,
}

export const DEFAULT_INFLUENCE_MIN_COMPARISONS = 10
export const INFLUENCE_MIN_COMPARISONS_FLOOR = 3
export const IDLE_FLUSH_MS = 90_000

export type CoherenceMethod = 'spearman' | 'kendall'

/** Minimal settings retained for local prefs / influence labels (no probe SoftMax). */
export interface RankingSettings {
  coherenceMethod: CoherenceMethod
}

export const defaultRankingSettings = (): RankingSettings => ({
  coherenceMethod: 'spearman',
})

export interface RankItem {
  id: number
  title: string
  description?: string | null
  active?: boolean
}

// Legacy type aliases kept so older imports compile during transition.
export type ObservationResponse = 'winner' | 'tie' | 'unsure' | 'skipped'
export type ObservationType = 'alternative' | 'criteria'
export interface Observation {
  id?: number | string
  type: ObservationType
  criterionId: number | null
  itemIds: number[]
  response: ObservationResponse
  winnerId?: number | null
  predictedId?: number | null
  predictedProbability?: number | null
  predictionCorrect?: boolean | null
  participant_id?: number
  _weight?: number
}

/** Minimal probe shape still referenced by vote-batch typing (sort UI owns real probes). */
export interface ProbeCandidate {
  type: ObservationType
  items: RankItem[]
  criterion: RankItem | null
  probability?: number
  predictedId: number
  predictedProbability?: number
  informationScore: number
  scenarioId?: string
}

export function normalizeParticipantInfluenceMode(mode?: string | null): ParticipantInfluenceMode {
  const m = String(mode || 'comparisons').trim().toLowerCase().replace(/[-\s]/g, '_')
  if (m === 'comparison' || m === 'equal_comparisons' || m === 'comparisons_equal') return 'comparisons'
  if (m === 'participant' || m === 'participants' || m === 'normalized' || m === 'participant_normalized') {
    return 'participants_normalized'
  }
  if ((PARTICIPANT_INFLUENCE_MODES as string[]).includes(m)) return m as ParticipantInfluenceMode
  return 'comparisons'
}

export function clampInfluenceMinComparisons(value?: number | null): number {
  const n = Math.round(Number(value ?? DEFAULT_INFLUENCE_MIN_COMPARISONS))
  if (!Number.isFinite(n)) return DEFAULT_INFLUENCE_MIN_COMPARISONS
  return Math.max(INFLUENCE_MIN_COMPARISONS_FLOOR, n)
}

export function clamp(value: number, lo = 0, hi = 1) {
  return Math.max(lo, Math.min(hi, value))
}

/** Convert API metric (0–1 fraction or already 0–100) to integer percent points. */
export function asMetricPercent(value: unknown): number {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n)) return 0
  if (n <= 1) return Math.round(n * 100)
  return Math.round(n)
}

/** Strong / Solid / … labels. Accepts 0–1 or 0–100. */
export function metricLabel(value: number) {
  const v = asMetricPercent(value)
  if (v >= 80) return 'Strong'
  if (v >= 60) return 'Solid'
  if (v >= 40) return 'Building'
  if (v >= 20) return 'Early'
  return 'Sparse'
}

/**
 * Format a ranking score as percent.
 * Server scores are normalized preference in [0, 1].
 * Values already > 1 are treated as percent points (defensive).
 */
export function formatPercent(score: number) {
  const n = Number(score)
  if (!Number.isFinite(n)) return '0%'
  if (n <= 1) return `${Math.round(n * 100)}%`
  return `${Math.round(n)}%`
}

/** Bar width 0–100 from a 0–1 (or 0–100) score. */
export function scoreBarPercent(score: number) {
  const n = Number(score)
  if (!Number.isFinite(n)) return 0
  if (n <= 1) return Math.max(0, Math.min(100, n * 100))
  return Math.max(0, Math.min(100, n))
}

/** Lead between two 0–1 scores as integer "points" (percent points). */
export function scoreLeadPoints(a: number, b: number) {
  return Math.round(Math.abs(scoreBarPercent(a) - scoreBarPercent(b)))
}

export function effectiveCriteria(criteria: RankItem[]): RankItem[] {
  const active = (criteria || []).filter(c => c.active !== false)
  if (active.length) return active
  return [{ id: 0, title: 'Overall' }]
}

export function mean(values: number[]) {
  if (!values.length) return 0
  return values.reduce((a, b) => a + b, 0) / values.length
}

export type RankingMode = 'find_best' | 'find_top_3' | 'find_top_half' | 'rank_all'

export function normalizeRankingMode(
  mode?: string | null,
  exclusive?: boolean | null,
): RankingMode {
  const m = String(mode || '').trim().toLowerCase().replace(/[-\s]/g, '_')
  if (m === 'find_best' || m === 'winner' || m === 'pick_one' || m === 'exclusive') return 'find_best'
  if (m === 'find_top_3' || m === 'top_3' || m === 'top3') return 'find_top_3'
  if (m === 'find_top_half' || m === 'top_half') return 'find_top_half'
  if (m === 'rank_all' || m === 'full' || m === 'rank') return 'rank_all'
  return exclusive ? 'find_best' : 'rank_all'
}

export function headlineOptionLabel(mode: RankingMode) {
  return mode === 'find_best' ? 'Recommended option' : 'Top option'
}

function finiteNumber(value: unknown): number | null {
  if (value == null || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/** Null when missing; treat exact 0 as empty when that value cannot be real. */
export function nullableUnit(value: unknown, treatZeroAsEmpty = false): number | null {
  const n = finiteNumber(value)
  if (n == null) return null
  if (treatZeroAsEmpty && n === 0) return null
  return n
}

export function formatNullablePercent(value: unknown, treatZeroAsEmpty = false) {
  const n = nullableUnit(value, treatZeroAsEmpty)
  if (n == null) return '—'
  return formatPercent(n)
}

/** 1-based rank_ci95 → "rank 2" or "ranks 1–3". */
export function formatRankCi(ci: unknown): string | null {
  if (!Array.isArray(ci) || ci.length < 2) return null
  const lo = finiteNumber(ci[0])
  const hi = finiteNumber(ci[1])
  if (lo == null || hi == null) return null
  const a = Math.max(1, Math.round(Math.min(lo, hi)))
  const b = Math.max(a, Math.round(Math.max(lo, hi)))
  if (a === b) return `rank ${a}`
  return `ranks ${a}–${b}`
}

export function formatWeightCi(ci: unknown): string | null {
  if (!Array.isArray(ci) || ci.length < 2) return null
  const lo = finiteNumber(ci[0])
  const hi = finiteNumber(ci[1])
  if (lo == null || hi == null) return null
  return `${formatPercent(lo)}–${formatPercent(hi)}`
}

export function formatExpectedRank(value: unknown): string | null {
  const n = finiteNumber(value)
  if (n == null) return null
  const rounded = Math.round(n * 10) / 10
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)
}

/** p_best in find_best; p_top_n in top-N modes; omit for rank_all. */
export function optionChanceCaption(
  row: { p_best?: unknown, p_top_n?: unknown } | null | undefined,
  mode: RankingMode,
  topN?: number | null,
): string | null {
  if (!row) return null
  if (mode === 'find_best') {
    const p = nullableUnit(row.p_best)
    if (p == null) return null
    return `${formatPercent(p)} chance it's #1`
  }
  if (mode === 'find_top_3' || mode === 'find_top_half') {
    const p = nullableUnit(row.p_top_n)
    if (p == null) return null
    const n = Math.max(1, finiteNumber(topN) || (mode === 'find_top_3' ? 3 : 1))
    return `${formatPercent(p)} chance in top ${n}`
  }
  return null
}

export function polarizingCaption(row: {
  polarizing?: unknown
  participant_rank_sd?: unknown
  title?: string
  expected_rank?: unknown
  rank?: unknown
} | null | undefined): string | null {
  if (!row) return null
  const sd = finiteNumber(row.participant_rank_sd)
  const flagged = row.polarizing === true || (sd != null && sd > 1.2)
  if (!flagged) return null
  const er = finiteNumber(row.expected_rank) ?? (finiteNumber(row.rank) != null ? Number(row.rank) + 1 : null)
  const rankLabel = er != null ? String(Math.round(er)) : '?'
  const title = String(row.title || 'This option')
  return `${title}: consensus #${rankLabel}, highly polarizing`
}

export interface InsightChip {
  key: 'agreement' | 'repeatability'
  label: string
  display: string
  caption: string
  empty: boolean
}

/**
 * Primary Results chips. Agreement = expected pair agreement.
 * Repeatability uses posterior same-winner vs same-top-N;
 * rank_all does not use same-top-N (it is always 1 when top_n = n).
 * Stability has been removed to avoid showing the same number twice
 * (for rank_all both derived from same-winner). See terminology_dictionary.md
 * Readiness metrics — keep Agreement + Repeatability only.
 */
export function insightMetricChips(report: Record<string, any> | null | undefined): InsightChip[] {
  const mode = normalizeRankingMode(report?.ranking_mode, report?.exclusive_mode)
  const coherence = report?.coherence && typeof report.coherence === 'object' ? report.coherence : {}
  const stab = report?.posterior_stability && typeof report.posterior_stability === 'object'
    ? report.posterior_stability
    : {}
  const comparisons = finiteNumber(report?.comparison_count ?? report?.total_observations) ?? 0
  const hasData = comparisons > 0
  const topN = Math.max(1, finiteNumber(report?.top_n) || 1)
  const nOptions = Array.isArray(report?.option_ranking) ? report.option_ranking.length : 0
  const topNInformative = nOptions > 1 && topN < nOptions

  const agreement = nullableUnit(coherence.expected_pair_agreement, true)
  const sameWinner = nullableUnit(stab.same_winner_repeat_probability, !hasData)
  const sameTopN = nullableUnit(stab.same_top_n_repeat_probability, !hasData)

  const useTopN = (mode === 'find_top_3' || mode === 'find_top_half') && topNInformative
  const repeatability = useTopN ? sameTopN : sameWinner

  const repeatCaption = useTopN
    ? `Same top ${topN} if these participants compared again`
    : 'Same winner if these participants compared again'

  return [
    {
      key: 'agreement',
      label: 'Agreement',
      display: agreement == null ? '—' : formatPercent(agreement),
      caption: agreement == null
        ? 'Not enough comparisons'
        : 'How often participants would pick the same pair the same way',
      empty: agreement == null,
    },
    {
      key: 'repeatability',
      label: 'Repeatability',
      display: repeatability == null ? '—' : formatPercent(repeatability),
      caption: repeatability == null ? 'Not enough comparisons' : repeatCaption,
      empty: repeatability == null,
    },
  ]
}

/** Map server ranking rows into a stable UI shape (score always 0–1). */
export function mapServerRanking(rows: any[] | undefined | null) {
  if (!Array.isArray(rows) || !rows.length) return null
  const n = rows.length
  return rows.map((r, i) => {
    // null mean_rank = option has no rank data in this slice (never compared under
    // the factor); keep it null so the UI shows an explicit "no data" row.
    const meanRank = r.mean_rank != null ? Number(r.mean_rank) : null
    let score = r.score != null ? Number(r.score) : NaN
    // Legacy rank-distance scores were in [0, n−1]
    if (Number.isFinite(score) && score > 1 && n > 1) {
      score = Math.max(0, Math.min(1, score / (n - 1)))
    }
    if (!Number.isFinite(score)) {
      score = meanRank != null && n > 1 ? Math.max(0, (n - 1 - meanRank) / (n - 1)) : 0
    }
    const weight = r.normalizedWeight ?? r.weight ?? r.normalized_weight
    const rankCi = Array.isArray(r.rank_ci95) ? r.rank_ci95.map(Number) : undefined
    const weightCi = Array.isArray(r.weight_ci95) ? r.weight_ci95.map(Number) : undefined
    return {
      id: r.id,
      title: r.title,
      description: r.description,
      score,
      mean_rank: meanRank,
      rank: r.rank ?? i,
      normalizedWeight: weight != null ? Number(weight) : undefined,
      weight: weight != null ? Number(weight) : undefined,
      confidence: r.confidence,
      stability: r.stability,
      pass_consistency: r.pass_consistency,
      leader: r.leader,
      data_points: r.data_points ?? r.evidence ?? 0,
      evidence: r.evidence ?? r.data_points ?? 0,
      expected_rank: finiteNumber(r.expected_rank),
      rank_sd: finiteNumber(r.rank_sd),
      median_rank: finiteNumber(r.median_rank),
      p_best: finiteNumber(r.p_best),
      p_top_n: finiteNumber(r.p_top_n),
      p_exact_rank: finiteNumber(r.p_exact_rank),
      rank_ci95: rankCi?.length === 2 && rankCi.every(Number.isFinite) ? rankCi : undefined,
      rank_entropy: finiteNumber(r.rank_entropy),
      pairwise_win_strength: finiteNumber(r.pairwise_win_strength),
      participant_rank_sd: finiteNumber(r.participant_rank_sd),
      polarizing: r.polarizing === true,
      weight_ci95: weightCi?.length === 2 && weightCi.every(Number.isFinite) ? weightCi : undefined,
      discrimination: finiteNumber(r.discrimination),
      leverage: finiteNumber(r.leverage),
      p_most_important: finiteNumber(r.p_most_important),
    }
  })
}

export interface PersonalSubmitterRankings {
  options: NonNullable<ReturnType<typeof mapServerRanking>>
  factors: NonNullable<ReturnType<typeof mapServerRanking>>
  rankingMode: RankingMode
  topN: number
  confidence: number | null
  showFactors: boolean
}

export function personalRankingsFromSummary(
  summary: Record<string, any> | null | undefined,
  projectSettings?: Record<string, unknown> | null,
): PersonalSubmitterRankings {
  const options = mapServerRanking(summary?.alternative_leaderboard) || []
  const factors = mapServerRanking(summary?.factor_leaderboard) || []
  const rankingMode = normalizeRankingMode(
    (projectSettings?.ranking_mode ?? summary?.ranking_mode) as string | undefined,
    (projectSettings?.project_exclusive_mode ?? summary?.exclusive_mode) as boolean | undefined,
  )
  const fromSummary = finiteNumber(summary?.top_n)
  const topN = Math.max(
    1,
    fromSummary ?? (rankingMode === 'find_top_3' ? 3 : 1),
  )
  return {
    options,
    factors,
    rankingMode,
    topN,
    confidence: finiteNumber(summary?.confidence),
    showFactors: factors.length > 1,
  }
}

/** JSON often stringifies numeric map keys; tolerate number | string | null. */
export function lookupRankMap<T>(
  maps: Record<string | number, T> | null | undefined,
  key: number | string | null | undefined,
): T | undefined {
  if (!maps || key === undefined) return undefined
  const rec = maps as Record<string | number, T>
  if (Object.prototype.hasOwnProperty.call(rec, key as PropertyKey)) return rec[key as keyof typeof rec]
  if (key === null) {
    if (Object.prototype.hasOwnProperty.call(rec, 'null')) return rec.null as T
    if (Object.prototype.hasOwnProperty.call(rec, 0)) return rec[0]
    if (Object.prototype.hasOwnProperty.call(rec, '0')) return rec['0']
    return undefined
  }
  const s = String(key)
  if (Object.prototype.hasOwnProperty.call(rec, s)) return rec[s]
  const n = Number(key)
  if (Number.isFinite(n) && Object.prototype.hasOwnProperty.call(rec, n)) return rec[n]
  return undefined
}

/**
 * Build a sorted ranking from a mean-rank map (lower mean_rank = better).
 * Used for per-participant per-factor #1s when only option_ranks_by_factor is present.
 */
export function rankingFromMeanRankMap(
  ranksMap: Record<string | number, number> | null | undefined,
  items: RankItem[],
): Array<{ id: number, title: string, mean_rank: number, rank: number, score: number }> {
  if (!ranksMap || !items?.length) return []
  const rows = items
    .map((item) => {
      const raw = lookupRankMap(ranksMap, item.id)
      if (raw == null) return null
      const meanRank = Number(raw)
      if (!Number.isFinite(meanRank)) return null
      return { id: item.id, title: item.title, mean_rank: meanRank }
    })
    .filter((r): r is { id: number, title: string, mean_rank: number } => r != null)
  rows.sort((a, b) => a.mean_rank - b.mean_rank || a.id - b.id)
  const n = rows.length
  return rows.map((r, i) => ({
    ...r,
    rank: i,
    score: n > 1 ? Math.max(0, Math.min(1, (n - 1 - r.mean_rank) / (n - 1))) : 1,
  }))
}

/**
 * All options tied for best in a ranking (shared best mean_rank, else shared best score).
 * Ranking lists break remaining ties by id for display order — concentration must not.
 */
export function tiedLeadersFromRanking(
  ranking: Array<{ id?: number, mean_rank?: number, score?: number, title?: string }> | null | undefined,
): Array<{ id: number, title: string }> {
  if (!ranking?.length) return []
  const rows = ranking
    .map(r => ({
      id: Number(r.id),
      title: String(r.title || ''),
      mean_rank: r.mean_rank != null ? Number(r.mean_rank) : NaN,
      score: r.score != null ? Number(r.score) : NaN,
    }))
    .filter(r => Number.isFinite(r.id))
  if (!rows.length) return []

  const withMean = rows.filter(r => Number.isFinite(r.mean_rank))
  if (withMean.length) {
    const best = Math.min(...withMean.map(r => r.mean_rank))
    return withMean
      .filter(r => Math.abs(r.mean_rank - best) < 1e-9)
      .map(r => ({ id: r.id, title: r.title }))
  }

  const withScore = rows.filter(r => Number.isFinite(r.score))
  if (!withScore.length) return [{ id: rows[0].id, title: rows[0].title }]
  const bestScore = Math.max(...withScore.map(r => r.score))
  return withScore
    .filter(r => Math.abs(r.score - bestScore) < 1e-9)
    .map(r => ({ id: r.id, title: r.title }))
}

/** #1 option(s) under a factor for one participant row from the report. */
export function participantLeadersUnderFactor(
  participant: any,
  factorId: number | null | undefined,
  items: RankItem[],
): Array<{ id: number, title: string }> {
  if (!participant) return []
  if (factorId == null) {
    const ranking = mapServerRanking(
      participant.option_ranking || participant.ranking,
    ) || []
    if (ranking.length) return tiedLeadersFromRanking(ranking)
    const leader = participant.leader
    if (leader && typeof leader === 'object' && leader.id != null) {
      return [{ id: Number(leader.id), title: String(leader.title || '') }]
    }
    return []
  }
  const ranks = lookupRankMap(participant.option_ranks_by_factor, factorId)
  const ranking = rankingFromMeanRankMap(ranks as Record<string | number, number> | undefined, items)
  return tiedLeadersFromRanking(ranking)
}

/** First #1 under a factor (display convenience). */
export function participantLeaderUnderFactor(
  participant: any,
  factorId: number | null | undefined,
  items: RankItem[],
): { id: number, title: string } | null {
  return participantLeadersUnderFactor(participant, factorId, items)[0] || null
}

export function mergeRankingSettings(
  ...sources: Array<Partial<RankingSettings> | Record<string, unknown> | null | undefined>
): RankingSettings {
  const base = defaultRankingSettings()
  for (const src of sources) {
    if (!src) continue
    const s = src as Record<string, unknown>
    if (s.coherenceMethod != null || s.coherence_method != null) {
      const m = String(s.coherenceMethod ?? s.coherence_method).toLowerCase()
      base.coherenceMethod = m === 'kendall' ? 'kendall' : 'spearman'
    }
  }
  return base
}
