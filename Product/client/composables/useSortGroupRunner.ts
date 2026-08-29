/**
 * Drive a server-issued compare group: adaptive pairs, undo, local recovery, packages.
 */
import type { PairResponse } from '~/utils/sortCompare'
import {
  chooseOrientation,
  rankOrderFromAnswers,
  selectNextPair,
  type PairAnswer,
  type RankingTarget,
  type SchedulerState,
} from '~/utils/pairScheduler'

export type SortGroupPayload = {
  client_group_id: string
  group_token?: string
  pass_index: number
  group_type: string
  criterion_id?: number | null
  criterion?: { id: number; title?: string; description?: string | null; comparison_question?: string | null } | null
  sort_algorithm?: string
  items: Array<{ id: number; title?: string; description?: string | null }>
  item_ids?: number[]
  n_items?: number
  estimated_comparisons?: number
  question_budget?: number
  ranking_target?: string
  top_n?: number | null
  require_coverage?: boolean
  prior_pairings?: Array<Record<string, unknown>>
  pairings?: Array<Record<string, unknown>>
  algorithm_version?: string
}

const LS_PREFIX = 'power-choice:v1:group:'

function tokenOf(g: SortGroupPayload): string {
  return String(g.group_token || g.client_group_id || '')
}

function parseStoredPairing(p: Record<string, unknown>): PairAnswer | null {
  const left = Number(p.presented_left_id ?? p.presentedLeftId ?? p.item_a_id ?? p.winner_id)
  const right = Number(p.presented_right_id ?? p.presentedRightId ?? p.item_b_id ?? p.loser_id)
  const a = Number(p.item_a_id ?? p.winner_id ?? left)
  const b = Number(p.item_b_id ?? p.loser_id ?? right)
  if (!Number.isFinite(a) || !Number.isFinite(b) || a === b) return null
  const response = String(p.response || 'winner') as PairResponse
  const winner = p.winner_id != null ? Number(p.winner_id) : (response === 'winner' ? a : null)
  return {
    itemA: a,
    itemB: b,
    winnerId: Number.isFinite(winner as number) ? Number(winner) : null,
    response,
    presentedLeftId: Number.isFinite(left) ? left : a,
    presentedRightId: Number.isFinite(right) ? right : b,
    decisionSeconds: Number(p.decision_seconds ?? p.decisionSeconds ?? 0) || 0,
  }
}

function longerHistory(a: PairAnswer[], b: PairAnswer[]): PairAnswer[] {
  return a.length >= b.length ? a : b
}

function loadLocal(token: string): PairAnswer[] {
  if (!token || !import.meta.client) return []
  try {
    const raw = localStorage.getItem(LS_PREFIX + token)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    const rows = Array.isArray(parsed?.pairings) ? parsed.pairings : []
    return rows.map((p: Record<string, unknown>) => parseStoredPairing(p)).filter(Boolean) as PairAnswer[]
  } catch {
    return []
  }
}

function saveLocal(token: string, answers: PairAnswer[]) {
  if (!token || !import.meta.client) return
  try {
    localStorage.setItem(LS_PREFIX + token, JSON.stringify({
      token,
      pairings: answers.map(toPairingPayload),
      updatedAt: new Date().toISOString(),
    }))
  } catch { /* ignore quota */ }
}

function clearLocal(token: string) {
  if (!token || !import.meta.client) return
  try { localStorage.removeItem(LS_PREFIX + token) } catch { /* ignore */ }
}

function toPairingPayload(a: PairAnswer) {
  const winner = a.response === 'winner' && a.winnerId != null
    ? a.winnerId
    : (a.itemA < a.itemB ? a.itemA : a.itemB)
  const loser = winner === a.itemA ? a.itemB : a.itemA
  return {
    winner_id: winner,
    loser_id: loser,
    item_a_id: a.itemA,
    item_b_id: a.itemB,
    response: a.response,
    decision_seconds: a.decisionSeconds,
    presented_left_id: a.presentedLeftId,
    presented_right_id: a.presentedRightId,
  }
}

function targetFromGroup(g: SortGroupPayload, n: number): RankingTarget {
  const mode = String(g.ranking_target || 'full')
  if (mode === 'winner') return { mode: 'winner', n: 1 }
  if (mode === 'top_n') return { mode: 'top_n', n: Math.max(1, Number(g.top_n || Math.floor(n / 2) || 1)) }
  return { mode: 'full' }
}

export function useSortGroupRunner() {
  const group = ref<SortGroupPayload | null>(null)
  const left = ref<{ id: number; title?: string; description?: string | null } | null>(null)
  const right = ref<{ id: number; title?: string; description?: string | null } | null>(null)
  const presentedLeftId = ref(0)
  const presentedRightId = ref(0)
  const answers = ref<PairAnswer[]>([])
  const priorAnswers = ref<PairAnswer[]>([])
  const inGroupDone = ref(0)
  const inGroupTotal = ref(0)
  const complete = ref(false)
  const shownAt = ref(0)
  const paused = ref(false)
  const pauseAccumMs = ref(0)
  const pauseStartedAt = ref(0)

  const pairings = computed(() => answers.value.map(toPairingPayload))

  const itemById = computed(() => {
    const m = new Map<number, { id: number; title?: string; description?: string | null }>()
    for (const it of group.value?.items || []) m.set(Number(it.id), it)
    return m
  })

  function itemIdsOf(g: SortGroupPayload): number[] {
    return (g.item_ids?.length ? g.item_ids : (g.items || []).map(i => i.id)).map(Number)
  }

  function currentState(): SchedulerState | null {
    const g = group.value
    if (!g) return null
    const items = itemIdsOf(g)
    return {
      items,
      target: targetFromGroup(g, items.length),
      passIndex: g.require_coverage === false ? Math.max(2, Number(g.pass_index || 1)) : Number(g.pass_index || 1),
      questionBudget: inGroupTotal.value,
      answers: answers.value,
      priorAnswers: priorAnswers.value,
      lastPair: answers.value.length
        ? [answers.value[answers.value.length - 1].itemA, answers.value[answers.value.length - 1].itemB]
        : null,
    }
  }

  function presentPair(a: number, b: number) {
    const g = group.value
    const hist = [...priorAnswers.value, ...answers.value]
    const sides = chooseOrientation(a, b, hist, [tokenOf(g!), a, b, answers.value.length])
    presentedLeftId.value = sides.left
    presentedRightId.value = sides.right
    left.value = itemById.value.get(sides.left) || { id: sides.left }
    right.value = itemById.value.get(sides.right) || { id: sides.right }
    shownAt.value = performance.now()
    pauseAccumMs.value = 0
  }

  function syncFromState() {
    const state = currentState()
    if (!state) return
    if (state.answers.length >= state.questionBudget) {
      complete.value = true
      left.value = null
      right.value = null
      inGroupDone.value = state.answers.length
      return
    }
    const next = selectNextPair(state)
    if (!next) {
      complete.value = true
      left.value = null
      right.value = null
      inGroupDone.value = state.answers.length
      return
    }
    complete.value = false
    presentPair(next[0], next[1])
    inGroupDone.value = state.answers.length
  }

  function persistLocal() {
    const g = group.value
    if (!g) return
    saveLocal(tokenOf(g), answers.value)
  }

  function startGroup(g: SortGroupPayload) {
    group.value = g
    complete.value = false
    const ids = itemIdsOf(g)
    inGroupTotal.value = Number(g.question_budget || g.estimated_comparisons || ids.length)
    const server = (g.pairings || []).map(p => parseStoredPairing(p)).filter(Boolean) as PairAnswer[]
    const local = loadLocal(tokenOf(g))
    answers.value = longerHistory(local, server)
    priorAnswers.value = (g.prior_pairings || []).map(p => parseStoredPairing(p)).filter(Boolean) as PairAnswer[]
    persistLocal()
    queueMicrotask(() => syncFromState())
  }

  function decisionSeconds(): number {
    const raw = performance.now() - shownAt.value - pauseAccumMs.value
    return Math.max(0, raw / 1000)
  }

  function answer(response: PairResponse, winnerId?: number) {
    if (!left.value || !right.value || complete.value || paused.value) return
    const lid = presentedLeftId.value
    const rid = presentedRightId.value
    const itemA = Math.min(lid, rid)
    const itemB = Math.max(lid, rid)
    answers.value = [...answers.value, {
      itemA,
      itemB,
      winnerId: response === 'winner' ? Number(winnerId) : null,
      response,
      presentedLeftId: lid,
      presentedRightId: rid,
      decisionSeconds: decisionSeconds(),
    }]
    persistLocal()
    left.value = null
    right.value = null
    queueMicrotask(() => syncFromState())
  }

  function undo() {
    if (!answers.value.length || complete.value) return false
    answers.value = answers.value.slice(0, -1)
    persistLocal()
    complete.value = false
    left.value = null
    right.value = null
    queueMicrotask(() => syncFromState())
    return true
  }

  function setPaused(v: boolean) {
    if (v && !paused.value) {
      pauseStartedAt.value = performance.now()
      paused.value = true
    } else if (!v && paused.value) {
      pauseAccumMs.value += performance.now() - pauseStartedAt.value
      paused.value = false
    }
  }

  function buildPackageBody(includeRank: boolean) {
    const g = group.value
    if (!g) return null
    const ids = itemIdsOf(g)
    const token = tokenOf(g)
    return {
      client_group_id: token,
      group_token: token,
      pass_index: Number(g.pass_index || 1),
      group_type: String(g.group_type || 'alternative'),
      criterion_id: g.criterion_id ?? null,
      sort_algorithm: String(g.sort_algorithm || 'ford_johnson'),
      item_ids_initial: ids,
      rank_order: includeRank ? rankOrderFromAnswers(ids, answers.value) : [],
      pairings: answers.value.map(toPairingPayload),
      algorithm_version: g.algorithm_version || '1.1-adaptive',
      event_timestamp: new Date().toISOString(),
    }
  }

  function buildPackage() {
    if (!complete.value) return null
    const pkg = buildPackageBody(true)
    const g = group.value
    if (g) clearLocal(tokenOf(g))
    return pkg
  }

  function buildPartialPackage() {
    if (!answers.value.length) return null
    return buildPackageBody(false)
  }

  function stop() {
    group.value = null
    left.value = null
    right.value = null
    answers.value = []
    priorAnswers.value = []
  }

  return {
    group,
    left,
    right,
    inGroupDone,
    inGroupTotal,
    complete,
    paused,
    pairings,
    startGroup,
    answer,
    undo,
    setPaused,
    buildPackage,
    buildPartialPackage,
    stop,
    canUndo: computed(() => answers.value.length > 0 && !complete.value),
  }
}
