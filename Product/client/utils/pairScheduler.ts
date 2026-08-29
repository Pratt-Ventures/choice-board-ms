/** Adaptive pairwise scheduler: acquisition heuristic only, not authoritative stats. */

import { fordJohnsonBudget, maxUniquePairs, type PairResponse } from './sortCompare.ts'

export type RankingTargetMode = 'winner' | 'top_n' | 'full'

export type PairAnswer = {
  itemA: number
  itemB: number
  winnerId: number | null
  response: PairResponse
  presentedLeftId: number
  presentedRightId: number
  decisionSeconds: number
}

export type RankingTarget = { mode: RankingTargetMode; n?: number }

export type SchedulerState = {
  items: number[]
  target: RankingTarget
  passIndex: number
  questionBudget: number
  answers: PairAnswer[]
  priorAnswers: PairAnswer[]
  lastPair: [number, number] | null
}

function pairKey(a: number, b: number): string {
  return a < b ? `${a},${b}` : `${b},${a}`
}

function hashSeed(parts: Array<string | number>): number {
  const s = parts.join('|')
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function seededUnit(seed: number): number {
  const x = Math.sin(seed) * 10000
  return x - Math.floor(x)
}

export function fitProvisionalScores(items: number[], answers: PairAnswer[]): Map<number, number> {
  const scores = new Map<number, number>()
  for (const id of items) scores.set(id, 0)
  const usable = answers.filter(a => a.response === 'winner' || a.response === 'tie')
  if (!usable.length) return scores
  const lr = 0.25
  const reg = 0.08
  for (let iter = 0; iter < 24; iter++) {
    const grad = new Map<number, number>()
    for (const id of items) grad.set(id, reg * (scores.get(id) || 0))
    for (const ans of usable) {
      const sa = scores.get(ans.itemA) || 0
      const sb = scores.get(ans.itemB) || 0
      const p = 1 / (1 + Math.exp(-(sa - sb)))
      const y = ans.response === 'tie' ? 0.5 : (ans.winnerId === ans.itemA ? 1 : 0)
      const g = p - y
      grad.set(ans.itemA, (grad.get(ans.itemA) || 0) + g)
      grad.set(ans.itemB, (grad.get(ans.itemB) || 0) - g)
    }
    for (const id of items) {
      scores.set(id, (scores.get(id) || 0) - lr * (grad.get(id) || 0))
    }
    const mean = items.reduce((s, id) => s + (scores.get(id) || 0), 0) / items.length
    for (const id of items) scores.set(id, (scores.get(id) || 0) - mean)
  }
  return scores
}

function ranksFromScores(items: number[], scores: Map<number, number>): Map<number, number> {
  const ordered = [...items].sort((a, b) => {
    const d = (scores.get(b) || 0) - (scores.get(a) || 0)
    return d !== 0 ? d : a - b
  })
  const ranks = new Map<number, number>()
  ordered.forEach((id, i) => ranks.set(id, i + 1))
  return ranks
}

function components(items: number[], edges: Array<[number, number]>): number[][] {
  const adj = new Map<number, number[]>()
  for (const id of items) adj.set(id, [])
  for (const [a, b] of edges) {
    adj.get(a)?.push(b)
    adj.get(b)?.push(a)
  }
  const seen = new Set<number>()
  const out: number[][] = []
  for (const id of items) {
    if (seen.has(id)) continue
    const stack = [id]
    const comp: number[] = []
    seen.add(id)
    while (stack.length) {
      const cur = stack.pop()!
      comp.push(cur)
      for (const nxt of adj.get(cur) || []) {
        if (!seen.has(nxt)) {
          seen.add(nxt)
          stack.push(nxt)
        }
      }
    }
    out.push(comp)
  }
  return out
}

function usedPairSet(answers: PairAnswer[]): Set<string> {
  const s = new Set<string>()
  for (const a of answers) s.add(pairKey(a.itemA, a.itemB))
  return s
}

function historicalStats(prior: PairAnswer[], a: number, b: number) {
  let count = 0
  let winsA = 0
  let winsB = 0
  for (const p of prior) {
    if (pairKey(p.itemA, p.itemB) !== pairKey(a, b)) continue
    count++
    if (p.response !== 'winner' || p.winnerId == null) continue
    if (p.winnerId === a) winsA++
    else if (p.winnerId === b) winsB++
  }
  return { count, winsA, winsB }
}

export function enumerateLegalPairs(state: SchedulerState): Array<[number, number]> {
  const used = usedPairSet(state.answers)
  const last = state.lastPair
  const all: Array<[number, number]> = []
  const disjoint: Array<[number, number]> = []
  for (let i = 0; i < state.items.length; i++) {
    for (let j = i + 1; j < state.items.length; j++) {
      const a = state.items[i]
      const b = state.items[j]
      if (used.has(pairKey(a, b))) continue
      all.push([a, b])
      if (!last || (a !== last[0] && a !== last[1] && b !== last[0] && b !== last[1])) {
        disjoint.push([a, b])
      }
    }
  }
  return disjoint.length ? disjoint : all
}

function unseenItems(state: SchedulerState): Set<number> {
  const seen = new Set<number>()
  for (const a of state.answers) {
    seen.add(a.itemA)
    seen.add(a.itemB)
  }
  return new Set(state.items.filter(id => !seen.has(id)))
}

function remainsFeasible(state: SchedulerState, pair: [number, number]): boolean {
  const remainingAfter = state.questionBudget - state.answers.length - 1
  if (remainingAfter <= 0) return true
  const next: SchedulerState = {
    ...state,
    answers: [...state.answers, {
      itemA: pair[0],
      itemB: pair[1],
      winnerId: pair[0],
      response: 'winner',
      presentedLeftId: pair[0],
      presentedRightId: pair[1],
      decisionSeconds: 0,
    }],
    lastPair: pair,
  }
  const legal = enumerateLegalPairs(next)
  if (!legal.length) return false
  if (state.passIndex === 1) {
    const unseen = unseenItems(next)
    if (unseen.size > remainingAfter * 2) return false
    if (unseen.size === 1) {
      const u = [...unseen][0]
      const canCover = legal.some(([a, b]) => a === u || b === u)
      if (!canCover && remainingAfter === 1) return false
    }
  }
  return true
}

function acquisitionScore(state: SchedulerState, pair: [number, number], scores: Map<number, number>, ranks: Map<number, number>): number {
  const [a, b] = pair
  const sa = scores.get(a) || 0
  const sb = scores.get(b) || 0
  const p = 1 / (1 + Math.exp(-(sa - sb)))
  const I = 4 * p * (1 - p)
  const ra = ranks.get(a) || 1
  const rb = ranks.get(b) || 1
  const n = state.items.length
  const topN = Math.max(1, Math.min(state.target.n || 1, Math.floor(n / 2) || 1))
  let T = 1
  if (state.target.mode === 'winner') {
    const Ta = Math.exp(-(ra - 1) / 2)
    const Tb = Math.exp(-(rb - 1) / 2)
    T = (Ta + Tb) / 2
    if (ra === 1 || rb === 1) T += 0.35
  } else if (state.target.mode === 'top_n') {
    const ordered = [...state.items].sort((x, y) => (ranks.get(x) || 0) - (ranks.get(y) || 0))
    const boundary = ordered.length > topN
      ? ((scores.get(ordered[topN - 1]) || 0) + (scores.get(ordered[topN]) || 0)) / 2
      : (scores.get(ordered[ordered.length - 1]) || 0)
    const Da = Math.exp(-Math.abs(sa - boundary) / 0.75)
    const Db = Math.exp(-Math.abs(sb - boundary) / 0.75)
    T = (Da + Db) / 2
    const straddles = (ra <= topN) !== (rb <= topN)
    if (straddles) T += 0.55
  } else {
    T = Math.exp(-(Math.abs(ra - rb) - 1) / 2.5)
  }
  const hist = historicalStats(state.priorAnswers, a, b)
  const R = 1 / Math.sqrt(1 + 0.65 * hist.count)
  const exposure = new Map<number, number>()
  for (const id of state.items) exposure.set(id, 0)
  for (const ans of state.answers) {
    exposure.set(ans.itemA, (exposure.get(ans.itemA) || 0) + 1)
    exposure.set(ans.itemB, (exposure.get(ans.itemB) || 0) + 1)
  }
  const E = 1 + 0.15 * (2 - Math.min(exposure.get(a) || 0, 2) - Math.min(exposure.get(b) || 0, 2))
  const edges: Array<[number, number]> = []
  for (const ans of [...state.priorAnswers, ...state.answers]) {
    if (ans.response === 'unsure' || ans.response === 'skipped') continue
    edges.push([ans.itemA, ans.itemB])
  }
  const comps = components(state.items, edges)
  const inSame = comps.some(c => c.includes(a) && c.includes(b))
  const G = inSame ? 1 : 2.4
  let bonus = 0
  if (hist.count >= 2 && hist.winsA && hist.winsB) bonus += 0.25
  return I * T * R * E * G + bonus
}

export function selectNextPair(state: SchedulerState): [number, number] | null {
  if (state.answers.length >= state.questionBudget) return null
  if (state.items.length < 2) return null
  const pairCap = maxUniquePairs(state.items.length)
  if (state.answers.length >= pairCap) return null
  let candidates = enumerateLegalPairs(state)
  if (!candidates.length) return null
  const requireCoverage = state.passIndex === 1
  const unseen = unseenItems(state)
  if (requireCoverage && unseen.size >= 2) {
    const bothUnseen = candidates.filter(([a, b]) => unseen.has(a) && unseen.has(b))
    if (bothUnseen.length) candidates = bothUnseen
  } else if (requireCoverage && unseen.size === 1) {
    const u = [...unseen][0]
    const cover = candidates.filter(([a, b]) => a === u || b === u)
    if (cover.length) candidates = cover
  }
  const feasible = candidates.filter(pair => remainsFeasible(state, pair))
  const pool = feasible.length ? feasible : candidates
  const allAnswers = [...state.priorAnswers, ...state.answers]
  const scores = fitProvisionalScores(state.items, allAnswers)
  const ranks = ranksFromScores(state.items, scores)
  let best = pool[0]
  let bestScore = -Infinity
  const seed = hashSeed([state.passIndex, state.questionBudget, ...state.items])
  pool.forEach((pair, i) => {
    let s = acquisitionScore(state, pair, scores, ranks)
    s += seededUnit(seed + i) * 1e-6
    if (s > bestScore) {
      bestScore = s
      best = pair
    }
  })
  return best
}

export function chooseOrientation(
  a: number,
  b: number,
  history: PairAnswer[],
  seedParts: Array<string | number>,
): { left: number; right: number } {
  let leftA = 0
  let leftB = 0
  for (const h of history) {
    if (h.presentedLeftId === a) leftA++
    if (h.presentedLeftId === b) leftB++
  }
  if (leftA < leftB) return { left: a, right: b }
  if (leftB < leftA) return { left: b, right: a }
  return seededUnit(hashSeed([...seedParts, a, b])) < 0.5
    ? { left: a, right: b }
    : { left: b, right: a }
}

export function rankOrderFromAnswers(items: number[], answers: PairAnswer[]): number[] {
  const scores = fitProvisionalScores(items, answers)
  return [...items].sort((a, b) => {
    const d = (scores.get(b) || 0) - (scores.get(a) || 0)
    return d !== 0 ? d : a - b
  })
}

export function suggestedBudget(n: number): number {
  return fordJohnsonBudget(n)
}
