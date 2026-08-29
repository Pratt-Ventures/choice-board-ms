/** Pair-comparison sort sessions: Ford–Johnson (n≤40) and merge sort (n>40). */

export type SortAlgorithm = 'ford_johnson' | 'merge_sort'
export type PairResponse = 'winner' | 'tie' | 'unsure' | 'skipped'

export interface SortPairing {
  winner_id: number
  loser_id: number
  response: PairResponse
  decision_seconds: number
  presented_left_id: number
  presented_right_id: number
  effective_rule: string
}

export interface PendingPair {
  leftId: number
  rightId: number
  a: number
  b: number
}

export interface SortSession {
  itemIds: number[]
  algorithm: SortAlgorithm
  nextPair(): PendingPair | null
  recordResult(args: {
    winnerId: number
    loserId: number
    response: PairResponse
    decisionSeconds: number
    presentedLeftId: number
    presentedRightId: number
  }): void
  undo(): boolean
  isComplete(): boolean
  rankOrder(): number[]
  comparisonsDone(): number
  estimatedTotal(): number
  pairings(): SortPairing[]
}

const FJ_MAX = 40

export function selectSortAlgorithm(n: number): SortAlgorithm {
  return n <= FJ_MAX ? 'ford_johnson' : 'merge_sort'
}

export const DEFAULT_QUESTIONS_PER_GROUP = 20

export function fordJohnsonBudget(n: number): number {
  if (n <= 1) return 0
  let total = 0
  for (let i = 1; i <= n; i++) total += Math.ceil(Math.log2((3 * i) / 4))
  return total
}

export function maxUniquePairs(n: number): number {
  if (n < 2) return 0
  return (n * (n - 1)) >> 1
}

export function questionBudgetBounds(n: number): { min: number; max: number; estimate: number } {
  const estimate = fordJohnsonBudget(n)
  if (estimate <= 0) return { min: 0, max: 0, estimate: 0 }
  const pairCap = maxUniquePairs(n)
  const min = Math.max(1, Math.min(pairCap, Math.ceil(estimate / 2)))
  const max = Math.max(min, Math.min(pairCap, estimate * 2))
  return { min, max, estimate }
}

export function clampMinExpectedPasses(value: unknown): number {
  const raw = Number(value)
  const v = Number.isFinite(raw) ? Math.trunc(raw) : 2
  return Math.min(5, Math.max(1, v))
}

export function clampMaxRecommendedPasses(value: unknown, minPasses: unknown): number {
  const lo = clampMinExpectedPasses(minPasses)
  const raw = Number(value)
  const v = Number.isFinite(raw) ? Math.trunc(raw) : lo
  return Math.min(10, Math.max(lo, v))
}

export function clampQuestionsPerGroup(
  value: unknown,
  n: number,
  fallback = DEFAULT_QUESTIONS_PER_GROUP,
): number {
  const { min, max } = questionBudgetBounds(n)
  const raw = Number(value)
  const v = Number.isFinite(raw) ? Math.trunc(raw) : fallback
  if (max <= 0) return Math.min(500, Math.max(1, v || fallback))
  return Math.min(max, Math.max(min, v))
}

export function defaultQuestionsPerGroupForN(n: number): number {
  if (n < 2) return DEFAULT_QUESTIONS_PER_GROUP
  const scaled = Math.round(fordJohnsonBudget(n) * 2 / 3)
  return clampQuestionsPerGroup(scaled, n)
}

export function resolveQuestionsPerGroup(
  value: unknown,
  n: number,
  explicit = false,
): number {
  if (!explicit) return defaultQuestionsPerGroupForN(n)
  return clampQuestionsPerGroup(value, n)
}

export function fordJohnsonUpperBound(n: number): number {
  if (n <= 1) return 0
  if (n === 2) return 1
  const lg = Math.ceil(Math.log2(n))
  return n * lg - (1 << lg) + 1
}

export function mergeSortUpperBound(n: number): number {
  if (n <= 1) return 0
  if (n === 2) return 1
  const lg = Math.ceil(Math.log2(n))
  return n * lg - n + 1
}

export function estimatedComparisons(n: number, algorithm?: SortAlgorithm): number {
  const algo = algorithm || selectSortAlgorithm(n)
  return algo === 'ford_johnson' ? fordJohnsonUpperBound(n) : mergeSortUpperBound(n)
}

function resolveSoft(
  a: number,
  b: number,
  response: PairResponse,
  chosenWinner?: number,
): { winner: number; loser: number; rule: string } {
  if (response === 'winner' && chosenWinner != null && (chosenWinner === a || chosenWinner === b)) {
    return { winner: chosenWinner, loser: chosenWinner === a ? b : a, rule: 'choice' }
  }
  const winner = a < b ? a : b
  return { winner, loser: winner === a ? b : a, rule: 'id_asc' }
}

function jacobsthal(k: number): number {
  if (k <= 0) return 0
  if (k === 1) return 1
  let a = 0
  let b = 1
  for (let i = 2; i <= k; i++) {
    const c = b + 2 * a
    a = b
    b = c
  }
  return b
}

type CmpFn = (a: number, b: number) => Promise<number>

/** Async Ford–Johnson producing best→worst order. */
async function fordJohnsonAsync(ids: number[], cmp: CmpFn): Promise<number[]> {
  if (ids.length <= 1) return ids.slice()
  if (ids.length === 2) {
    const w = await cmp(ids[0], ids[1])
    return [w, w === ids[0] ? ids[1] : ids[0]]
  }
  const pairs: Array<[number, number]> = []
  const leftover = ids.length % 2 === 1 ? ids[ids.length - 1] : null
  const nPairs = Math.floor(ids.length / 2)
  for (let i = 0; i < nPairs; i++) {
    const a = ids[i * 2]
    const b = ids[i * 2 + 1]
    const w = await cmp(a, b)
    pairs.push([w, w === a ? b : a])
  }
  const winners = pairs.map((p) => p[0])
  const main = await fordJohnsonAsync(winners, cmp)
  const loserOf = new Map(pairs.map(([w, l]) => [w, l]))

  const losersOrdered: number[] = []
  const inserted = new Set<number>()
  if (main.length) {
    const fl = loserOf.get(main[0])
    if (fl != null) {
      losersOrdered.push(fl)
      inserted.add(fl)
    }
  }
  let k = 1
  while (inserted.size < pairs.length) {
    const jk = jacobsthal(k + 1)
    const jkPrev = jacobsthal(k)
    const hi = Math.min(jk, main.length) - 1
    const lo = jkPrev
    for (let i = hi; i >= lo; i--) {
      if (i < 0 || i >= main.length) continue
      const l = loserOf.get(main[i])
      if (l != null && !inserted.has(l)) {
        losersOrdered.push(l)
        inserted.add(l)
      }
    }
    k++
    if (k > 64) break
  }
  for (const [, l] of pairs) {
    if (!inserted.has(l)) {
      losersOrdered.push(l)
      inserted.add(l)
    }
  }

  /**
   * Insert into main (best→worst). Item is known no better than main[minIndex - 1]
   * when minIndex > 0 — i.e. must land at index >= minIndex.
   * Critical: a loser of winner W must use minIndex = index(W) + 1 (strictly after W).
   */
  async function binaryInsert(item: number, minIndex: number) {
    let lo = Math.max(0, Math.min(minIndex, main.length))
    let hi = main.length
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      const better = await cmp(item, main[mid])
      if (better === item) hi = mid
      else lo = mid + 1
    }
    main.splice(lo, 0, item)
  }

  for (const loser of losersOrdered) {
    let pairedWinner: number | null = null
    for (const [w, l] of pairs) {
      if (l === loser) {
        pairedWinner = w
        break
      }
    }
    const wi = pairedWinner != null ? main.indexOf(pairedWinner) : -1
    // Loser is strictly worse than its paired winner → insert only after that winner.
    const minIdx = wi < 0 ? 0 : wi + 1
    await binaryInsert(loser, minIdx)
  }
  if (leftover != null) await binaryInsert(leftover, 0)
  return main
}

async function mergeSortAsync(ids: number[], cmp: CmpFn): Promise<number[]> {
  if (ids.length <= 1) return ids.slice()
  const mid = ids.length >> 1
  const left = await mergeSortAsync(ids.slice(0, mid), cmp)
  const right = await mergeSortAsync(ids.slice(mid), cmp)
  const out: number[] = []
  let i = 0
  let j = 0
  while (i < left.length && j < right.length) {
    const w = await cmp(left[i], right[j])
    if (w === left[i]) out.push(left[i++])
    else out.push(right[j++])
  }
  while (i < left.length) out.push(left[i++])
  while (j < right.length) out.push(right[j++])
  return out
}

/**
 * Queue-driven session: algorithm runs async and blocks on each comparison.
 * nextPair() returns the current pending pair; recordResult unblocks.
 */
export function createSortSession(itemIds: number[], algorithm?: SortAlgorithm): SortSession {
  const ids = itemIds.map(Number).filter((n) => Number.isFinite(n))
  const algo = algorithm || selectSortAlgorithm(ids.length)
  const pairingsLog: SortPairing[] = []
  let pending: PendingPair | null = null
  let waiter: ((w: number) => void) | null = null
  let rank: number[] = []
  let done = false
  let failed: Error | null = null
  const answers: SortPairing[] = []

  const cmp: CmpFn = (a, b) =>
    new Promise<number>((resolve) => {
      pending = { a, b, leftId: a, rightId: b }
      waiter = (winner: number) => {
        pending = null
        waiter = null
        resolve(winner)
      }
    })

  const run = async () => {
    try {
      if (ids.length <= 1) {
        rank = ids.slice()
      } else if (algo === 'ford_johnson') {
        rank = await fordJohnsonAsync(ids, cmp)
      } else {
        rank = await mergeSortAsync(ids, cmp)
      }
    } catch (e) {
      failed = e as Error
      rank = ids.slice()
    } finally {
      done = true
      pending = null
      waiter = null
    }
  }

  // kick off
  void run()

  function nextPair(): PendingPair | null {
    if (done) return null
    return pending
  }

  function recordResult(args: {
    winnerId: number
    loserId: number
    response: PairResponse
    decisionSeconds: number
    presentedLeftId: number
    presentedRightId: number
  }) {
    if (!pending || !waiter) return
    const { a, b } = pending
    const soft = resolveSoft(a, b, args.response, args.response === 'winner' ? args.winnerId : undefined)
    const entry: SortPairing = {
      winner_id: soft.winner,
      loser_id: soft.loser,
      response: args.response,
      decision_seconds: args.decisionSeconds,
      presented_left_id: args.presentedLeftId,
      presented_right_id: args.presentedRightId,
      effective_rule: soft.rule,
    }
    pairingsLog.push(entry)
    answers.push(entry)
    const w = soft.winner
    waiter(w)
  }

  function undo(): boolean {
    if (!answers.length || done) return false
    // Full rebuild from answers[:-1]
    const keep = answers.slice(0, -1)
    answers.length = 0
    pairingsLog.length = 0
    pending = null
    waiter = null
    rank = []
    done = false
    failed = null
    // Restart algorithm and replay
    const replay = keep.slice()
    void (async () => {
      await run()
    })()
    // Synchronously we can't wait; use blocking replay via microtask chain
    // Better approach: recreate session-like by sequential promise pump
    return rebuildFrom(replay)
  }

  function rebuildFrom(replay: SortPairing[]): boolean {
    // Cancel is hard with async; recreate internal state by new session pattern:
    // For undo we restart run and feed answers on each pending via queueMicrotask loop
    pairingsLog.length = 0
    answers.length = 0
    pending = null
    waiter = null
    rank = []
    done = false
    let idx = 0
    const pump = () => {
      if (idx >= replay.length) return
      // wait until pending appears
      const tryFeed = () => {
        if (done) return
        if (!pending || !waiter) {
          queueMicrotask(tryFeed)
          return
        }
        const p = replay[idx++]
        recordResult({
          winnerId: p.winner_id,
          loserId: p.loser_id,
          response: p.response,
          decisionSeconds: p.decision_seconds,
          presentedLeftId: p.presented_left_id,
          presentedRightId: p.presented_right_id,
        })
        if (idx < replay.length) queueMicrotask(tryFeed)
      }
      queueMicrotask(tryFeed)
    }
    void run().then(() => {})
    // re-assign run is wrong since run already closed over. Simpler undo:
    return false
  }

  // Simpler undo: expose flag and let caller recreate session with previous pairings
  // Implement proper undo by storing and replaying on a fresh engine:

  return {
    itemIds: ids,
    algorithm: algo,
    nextPair,
    recordResult,
    undo: () => {
      // Not reliable with concurrent async; UI should keep pairing stack and recreate session
      if (!pairingsLog.length) return false
      pairingsLog.pop()
      answers.pop()
      return false // signal caller to recreate
    },
    isComplete: () => done && !failed,
    rankOrder: () => rank.slice(),
    comparisonsDone: () => pairingsLog.length,
    estimatedTotal: () => estimatedComparisons(ids.length, algo),
    pairings: () => pairingsLog.slice(),
  }
}

/** Create session and allow undo by full recreate (recommended). */
export function createSortSessionWithReplay(
  itemIds: number[],
  algorithm: SortAlgorithm | undefined,
  priorPairings: SortPairing[],
): SortSession {
  const session = createSortSession(itemIds, algorithm)
  if (!priorPairings.length) return wrapUndo(session, itemIds, algorithm, priorPairings)

  // Replay prior answers asynchronously
  const queue = priorPairings.slice()
  const feed = () => {
    if (!queue.length) return
    const pair = session.nextPair()
    if (!pair) {
      queueMicrotask(feed)
      return
    }
    const p = queue.shift()!
    session.recordResult({
      winnerId: p.winner_id,
      loserId: p.loser_id,
      response: p.response,
      decisionSeconds: p.decision_seconds,
      presentedLeftId: p.presented_left_id,
      presentedRightId: p.presented_right_id,
    })
    if (queue.length) queueMicrotask(feed)
  }
  queueMicrotask(feed)
  return wrapUndo(session, itemIds, algorithm, priorPairings)
}

function wrapUndo(
  session: SortSession,
  itemIds: number[],
  algorithm: SortAlgorithm | undefined,
  _initial: SortPairing[],
): SortSession {
  let current = session
  let log = () => current.pairings()
  return {
    get itemIds() {
      return current.itemIds
    },
    get algorithm() {
      return current.algorithm
    },
    nextPair: () => current.nextPair(),
    recordResult: (a) => current.recordResult(a),
    undo: () => {
      const prev = log()
      if (!prev.length) return false
      const kept = prev.slice(0, -1)
      current = createSortSessionWithReplay(itemIds, algorithm, kept)
      return true
    },
    isComplete: () => current.isComplete(),
    rankOrder: () => current.rankOrder(),
    comparisonsDone: () => current.comparisonsDone(),
    estimatedTotal: () => current.estimatedTotal(),
    pairings: () => current.pairings(),
  }
}

export function shufflePresentation(a: number, b: number): { leftId: number; rightId: number } {
  if (Math.random() < 0.5) return { leftId: a, rightId: b }
  return { leftId: b, rightId: a }
}
