/** Display-only session ranking confidence from this participant’s pairings. */

import { fordJohnsonBudget } from './sortCompare.ts'
import {
  fitProvisionalScores,
  rankOrderFromAnswers,
  type PairAnswer,
  type RankingTarget,
  type RankingTargetMode,
} from './pairScheduler.ts'

export const CONFIDENCE_LEVELS = ['none', 'low', 'moderate', 'fair', 'good', 'strong'] as const
export type ConfidenceLevel = (typeof CONFIDENCE_LEVELS)[number]

export const CONFIDENCE_LABELS: Record<ConfidenceLevel, string> = {
  none: 'None',
  low: 'Low',
  moderate: 'Moderate',
  fair: 'Fair',
  good: 'Good',
  strong: 'Strong',
}

const COVERAGE_W = 0.7
const CONSISTENCY_W = 0.2
const DECISIVENESS_W = 0.1
const LN2 = Math.log(2)

export type RankingEvidencePairing = PairAnswer | Record<string, unknown>

export type RankingEvidenceGroup = {
  group_type: string
  criterion_id?: number | null
  pass_index?: number
  item_ids?: number[]
  pairings?: RankingEvidencePairing[]
  question_budget?: number
  ranking_target?: string
  top_n?: number | null
  client_group_id?: string | null
}

export type RankingConfidence = {
  value: number
  pct: number
  level: ConfidenceLevel
  label: string
  color: string
}

export type RankingConfidenceInput = {
  evidence?: RankingEvidenceGroup[]
  optionIds?: number[]
  factorIds?: number[]
  defaultTarget?: RankingTarget
}

type ChannelKey = { group_type: string; criterion_id: number | null }

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(1, n))
}

function uniqueIds(ids: Array<number | null | undefined>): number[] {
  const out: number[] = []
  const seen = new Set<number>()
  for (const raw of ids) {
    const n = Number(raw)
    if (!Number.isFinite(n) || n === 0 || seen.has(n)) continue
    seen.add(n)
    out.push(n)
  }
  return out
}

function pairKey(a: number, b: number): string {
  return a < b ? `${a},${b}` : `${b},${a}`
}

function asInt(v: unknown): number | null {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export function pairingToAnswer(p: RankingEvidencePairing | null | undefined): PairAnswer | null {
  if (!p || typeof p !== 'object') return null
  const rec = p as Record<string, unknown>
  if (typeof rec.itemA === 'number' && typeof rec.itemB === 'number') {
    const itemA = Number(rec.itemA)
    const itemB = Number(rec.itemB)
    if (!Number.isFinite(itemA) || !Number.isFinite(itemB) || itemA === itemB) return null
    const response = String(rec.response || 'winner')
    return {
      itemA,
      itemB,
      winnerId: rec.winnerId == null ? null : Number(rec.winnerId),
      response: response as PairAnswer['response'],
      presentedLeftId: Number(rec.presentedLeftId ?? itemA),
      presentedRightId: Number(rec.presentedRightId ?? itemB),
      decisionSeconds: Number(rec.decisionSeconds ?? 0) || 0,
    }
  }
  const left = asInt(rec.presented_left_id ?? rec.presentedLeftId ?? rec.item_a_id ?? rec.winner_id)
  const right = asInt(rec.presented_right_id ?? rec.presentedRightId ?? rec.item_b_id ?? rec.loser_id)
  const a = asInt(rec.item_a_id ?? rec.winner_id ?? left)
  const b = asInt(rec.item_b_id ?? rec.loser_id ?? right)
  if (a == null || b == null || a === b) return null
  const response = String(rec.response || 'winner') as PairAnswer['response']
  const winnerRaw = rec.winner_id != null ? Number(rec.winner_id) : (response === 'winner' ? a : null)
  return {
    itemA: a,
    itemB: b,
    winnerId: Number.isFinite(winnerRaw as number) ? Number(winnerRaw) : null,
    response,
    presentedLeftId: left ?? a,
    presentedRightId: right ?? b,
    decisionSeconds: Number(rec.decision_seconds ?? rec.decisionSeconds ?? 0) || 0,
  }
}

function answersOf(pairings: RankingEvidencePairing[] | undefined): PairAnswer[] {
  const out: PairAnswer[] = []
  for (const p of pairings || []) {
    const ans = pairingToAnswer(p)
    if (ans) out.push(ans)
  }
  return out
}

function isDecisive(ans: PairAnswer): boolean {
  return ans.response === 'winner' || ans.response === 'tie'
}

function channelId(cid: unknown): number | null {
  if (cid == null || cid === '') return null
  const n = Number(cid)
  return Number.isFinite(n) ? n : null
}

function sameChannel(a: ChannelKey, b: ChannelKey): boolean {
  return a.group_type === b.group_type && a.criterion_id === b.criterion_id
}

function targetFromGroup(g: RankingEvidenceGroup, n: number, fallback?: RankingTarget): RankingTarget {
  const mode = String(g.ranking_target || fallback?.mode || 'full')
  if (mode === 'winner') return { mode: 'winner', n: 1 }
  if (mode === 'top_n') {
    const top = Number(g.top_n || fallback?.n || Math.floor(n / 2) || 1)
    return { mode: 'top_n', n: Math.max(1, top) }
  }
  return { mode: 'full' }
}

function coverageScore(answers: PairAnswer[], pairsNeeded: number): number {
  if (pairsNeeded <= 0) return 0
  const seen = new Set<string>()
  for (const ans of answers) {
    if (!isDecisive(ans)) continue
    seen.add(pairKey(ans.itemA, ans.itemB))
  }
  return clamp01(seen.size / pairsNeeded)
}

function repeatedPairAgreement(answers: PairAnswer[]): number | null {
  const buckets = new Map<string, string[]>()
  for (const ans of answers) {
    if (!isDecisive(ans)) continue
    const key = pairKey(ans.itemA, ans.itemB)
    let outcome = 'tie'
    if (ans.response === 'winner' && ans.winnerId != null) {
      outcome = String(ans.winnerId)
    }
    const list = buckets.get(key) || []
    list.push(outcome)
    buckets.set(key, list)
  }
  const repeats = [...buckets.values()].filter(list => list.length >= 2)
  if (!repeats.length) return null
  let sum = 0
  for (const list of repeats) {
    const counts = new Map<string, number>()
    for (const o of list) counts.set(o, (counts.get(o) || 0) + 1)
    const majority = Math.max(...counts.values())
    sum += majority / list.length
  }
  return clamp01(sum / repeats.length)
}

function preferenceMass(order: number[]): Map<number, number> {
  const n = order.length
  const raw = new Map<number, number>()
  let total = 0
  order.forEach((id, i) => {
    const w = Math.max(1e-12, n - i)
    raw.set(id, w)
    total += w
  })
  const out = new Map<number, number>()
  const denom = total || 1
  for (const [id, w] of raw) out.set(id, w / denom)
  return out
}

function kl(p: Map<number, number>, q: Map<number, number>, keys: number[]): number {
  const eps = 1e-12
  let sp = 0
  let sq = 0
  const ps: number[] = []
  const qs: number[] = []
  for (const k of keys) {
    const a = (p.get(k) || 0) + eps
    const b = (q.get(k) || 0) + eps
    ps.push(a)
    qs.push(b)
    sp += a
    sq += b
  }
  let s = 0
  for (let i = 0; i < keys.length; i++) {
    const a = ps[i] / sp
    const b = qs[i] / sq
    s += a * Math.log(a / b)
  }
  return s
}

function jsAgreement(orders: number[][]): number {
  if (orders.length < 2) return 0
  const dists = orders.filter(o => o.length).map(preferenceMass)
  if (dists.length < 2) return 0
  const keys = [...new Set(dists.flatMap(d => [...d.keys()]))]
  if (!keys.length) return 0
  const divs: number[] = []
  for (let i = 0; i < dists.length; i++) {
    for (let j = i + 1; j < dists.length; j++) {
      const m = new Map<number, number>()
      for (const k of keys) m.set(k, 0.5 * ((dists[i].get(k) || 0) + (dists[j].get(k) || 0)))
      divs.push(0.5 * kl(dists[i], m, keys) + 0.5 * kl(dists[j], m, keys))
    }
  }
  const mean = divs.length ? divs.reduce((a, b) => a + b, 0) / divs.length : 0
  return clamp01(1 - mean / LN2)
}

function consistencyScore(groups: RankingEvidenceGroup[], items: number[]): number | null {
  const allAnswers = groups.flatMap(g => answersOf(g.pairings))
  const repeated = repeatedPairAgreement(allAnswers)
  if (repeated != null) return repeated
  const byPass = new Map<number, PairAnswer[]>()
  for (const g of groups) {
    const pass = Math.max(1, Number(g.pass_index || 1))
    const list = byPass.get(pass) || []
    list.push(...answersOf(g.pairings))
    byPass.set(pass, list)
  }
  if (byPass.size < 2) return null
  const orders: number[][] = []
  for (const answers of byPass.values()) {
    const usable = answers.filter(isDecisive)
    if (!usable.length) continue
    orders.push(rankOrderFromAnswers(items, answers))
  }
  if (orders.length < 2) return null
  return jsAgreement(orders)
}

function decisivenessScore(items: number[], answers: PairAnswer[], target: RankingTarget): number {
  const usable = answers.filter(isDecisive)
  if (!usable.length || items.length < 2) return 0
  const scores = fitProvisionalScores(items, answers)
  const ordered = [...items].sort((a, b) => {
    const d = (scores.get(b) || 0) - (scores.get(a) || 0)
    return d !== 0 ? d : a - b
  })
  let hi = 0
  let lo = 1
  if (target.mode === 'top_n') {
    const n = Math.max(1, Math.min(target.n || 1, ordered.length - 1))
    hi = n - 1
    lo = n
  }
  const gap = Math.abs((scores.get(ordered[hi]) || 0) - (scores.get(ordered[lo]) || 0))
  return clamp01(1 - Math.exp(-gap))
}

function blendChannel(coverage: number, consistency: number | null, decisiveness: number): number {
  if (consistency == null) {
    const denom = COVERAGE_W + DECISIVENESS_W
    return clamp01((COVERAGE_W * coverage + DECISIVENESS_W * decisiveness) / denom)
  }
  return clamp01(COVERAGE_W * coverage + CONSISTENCY_W * consistency + DECISIVENESS_W * decisiveness)
}

function expectedChannels(optionIds: number[], factorIds: number[], evidence: RankingEvidenceGroup[]): ChannelKey[] {
  if (factorIds.length >= 2) {
    return [
      ...factorIds.map(fid => ({ group_type: 'alternative', criterion_id: fid })),
      { group_type: 'criteria', criterion_id: null },
    ]
  }
  if (factorIds.length === 1) {
    return [{ group_type: 'alternative', criterion_id: factorIds[0] }]
  }
  if (optionIds.length >= 2) {
    return [{ group_type: 'alternative', criterion_id: null }]
  }
  const seen = new Map<string, ChannelKey>()
  for (const g of evidence) {
    const key: ChannelKey = {
      group_type: String(g.group_type || 'alternative'),
      criterion_id: channelId(g.criterion_id),
    }
    seen.set(`${key.group_type}:${key.criterion_id ?? 'n'}`, key)
  }
  return [...seen.values()]
}

function pairsNeededFor(groups: RankingEvidenceGroup[], items: number[]): number {
  const budgets = groups.map(g => Number(g.question_budget || 0)).filter(n => n > 0)
  if (budgets.length) {
    const minPass = Math.min(...groups.map(g => Math.max(1, Number(g.pass_index || 1))))
    const firstPass = groups.filter(g => Math.max(1, Number(g.pass_index || 1)) === minPass)
    const sum = firstPass.reduce((s, g) => s + Math.max(0, Number(g.question_budget || 0)), 0)
    if (sum > 0) return sum
    return Math.max(...budgets)
  }
  return Math.max(1, fordJohnsonBudget(items.length))
}

function scoreChannel(
  channel: ChannelKey,
  groups: RankingEvidenceGroup[],
  fallbackTarget?: RankingTarget,
): number {
  const items = uniqueIds(groups.flatMap(g => g.item_ids || []))
  const answers = groups.flatMap(g => answersOf(g.pairings))
  if (items.length < 2 && !answers.length) return 0
  const target = groups.length ? targetFromGroup(groups[0], items.length, fallbackTarget) : (fallbackTarget || { mode: 'full' as RankingTargetMode })
  const needed = pairsNeededFor(groups, items)
  const coverage = coverageScore(answers, needed)
  const consistency = consistencyScore(groups, items)
  const decisiveness = decisivenessScore(items.length ? items : uniqueIds(answers.flatMap(a => [a.itemA, a.itemB])), answers, target)
  return blendChannel(coverage, consistency, decisiveness)
}

export function confidenceLevelFromValue(value: number): ConfidenceLevel {
  const v = clamp01(value)
  if (v <= 0) return 'none'
  if (v <= 0.2) return 'low'
  if (v <= 0.4) return 'moderate'
  if (v <= 0.6) return 'fair'
  if (v <= 0.8) return 'good'
  return 'strong'
}

export function interpolateConfidenceColor(value: number): string {
  const t = clamp01(value)
  if (t <= 0.5) {
    const warning = Math.round(t * 2 * 100)
    return `color-mix(in srgb, var(--pc-danger) ${100 - warning}%, var(--pc-warning) ${warning}%)`
  }
  const success = Math.round((t - 0.5) * 2 * 100)
  return `color-mix(in srgb, var(--pc-warning) ${100 - success}%, var(--pc-success) ${success}%)`
}

export function emptyRankingConfidence(): RankingConfidence {
  return {
    value: 0,
    pct: 0,
    level: 'none',
    label: CONFIDENCE_LABELS.none,
    color: interpolateConfidenceColor(0),
  }
}

export function evidenceGroupKey(g: RankingEvidenceGroup): string {
  const token = String(g.client_group_id || '').trim()
  if (token) return `token:${token}`
  const cid = g.criterion_id == null ? 'n' : String(g.criterion_id)
  const ids = uniqueIds(g.item_ids || []).slice().sort((a, b) => a - b).join(',')
  return `${g.group_type}|${cid}|${Math.max(1, Number(g.pass_index || 1))}|${ids}`
}

export function mergeLiveEvidence(
  evidence: RankingEvidenceGroup[],
  live: RankingEvidenceGroup | null | undefined,
): RankingEvidenceGroup[] {
  if (!live) return evidence
  const key = evidenceGroupKey(live)
  return [...evidence.filter(g => evidenceGroupKey(g) !== key), live]
}

export function evidenceFromLiveGroup(
  group: {
    client_group_id?: string
    group_token?: string
    group_type?: string
    criterion_id?: number | null
    pass_index?: number
    item_ids?: number[]
    items?: Array<{ id: number }>
    question_budget?: number
    estimated_comparisons?: number
    ranking_target?: string
    top_n?: number | null
  } | null | undefined,
  pairings: RankingEvidencePairing[] | undefined,
): RankingEvidenceGroup | null {
  if (!group) return null
  const itemIds = uniqueIds(
    (group.item_ids?.length ? group.item_ids : (group.items || []).map(i => i.id)),
  )
  return {
    group_type: String(group.group_type || 'alternative'),
    criterion_id: channelId(group.criterion_id),
    pass_index: Math.max(1, Number(group.pass_index || 1)),
    item_ids: itemIds,
    pairings: pairings || [],
    question_budget: Number(group.question_budget || group.estimated_comparisons || 0),
    ranking_target: group.ranking_target,
    top_n: group.top_n ?? null,
    client_group_id: String(group.group_token || group.client_group_id || '') || null,
  }
}

export function computeRankingConfidence(input: RankingConfidenceInput = {}): RankingConfidence {
  const evidence = Array.isArray(input.evidence) ? input.evidence : []
  const optionIds = uniqueIds(input.optionIds || [])
  const factorIds = uniqueIds(input.factorIds || [])
  const channels = expectedChannels(optionIds, factorIds, evidence)
  if (!channels.length) return emptyRankingConfidence()
  const scores = channels.map((ch) => {
    const groups = evidence.filter(g => sameChannel(
      { group_type: String(g.group_type || 'alternative'), criterion_id: channelId(g.criterion_id) },
      ch,
    ))
    return scoreChannel(ch, groups, input.defaultTarget)
  })
  const value = clamp01(scores.reduce((a, b) => a + b, 0) / scores.length)
  const level = confidenceLevelFromValue(value)
  return {
    value,
    pct: Math.round(value * 100),
    level,
    label: CONFIDENCE_LABELS[level],
    color: interpolateConfidenceColor(value),
  }
}
