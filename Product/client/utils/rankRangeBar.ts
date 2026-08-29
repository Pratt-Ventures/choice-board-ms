/**
 * Geometry for the self-view expected-rank range bar.
 *
 * Paints a compact horizontal rank axis (1…N) with a color gradient peaking at
 * the posterior expected rank and fading to the background at ±2 SD. Pure math
 * only — RankRangeBar.vue turns the model into markup.
 */

export interface RankRangeBarInput {
  expectedRank?: number | null
  rankSd?: number | null
  /** 95% rank interval (1-based); used to approximate SD when rank_sd is missing. */
  rankCi95?: number[] | null
  /** Number of ranked items; defines the axis extent. */
  itemCount: number
}

export interface RankGradientStop {
  /** Percent within the painted band (0–100). */
  offset: number
  /** Peak color intensity 0–1 at this stop. */
  alpha: number
}

export interface RankTick {
  /** Percent across the full axis (0–100). */
  offset: number
  /** Numeric label; null for unlabeled minor ticks. */
  label: string | null
}

export interface RankRangeBarModel {
  bandStart: number
  bandEnd: number
  stops: RankGradientStop[]
  ticks: RankTick[]
  /** Axis percent of the expected-rank peak. */
  peakOffset: number
}

/** Gradient reaches zero intensity at mean ± this many SDs. */
export const RANGE_BAR_SD_SPAN = 2
/** 7 gradient stops: mean, ±⅔ SD, ±4⁄3 SD, ±2 SD. */
export const RANGE_BAR_STOP_ALPHAS = [0, 0.15, 0.45, 0.88, 0.45, 0.15, 0]
/** Smallest painted band (in rank units) so near-certain items stay visible. */
export const RANGE_BAR_MIN_SPAN = 0.2

const TICK_BUDGET = 9

/** Effective budget for tick generation — raised to N+1 so every rank gets a mark in typical projects. */
function effectiveTickBudget(itemCount: number): number {
  return Math.max(TICK_BUDGET, itemCount + 1)
}

function finite(value: unknown): number | null {
  if (value == null || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/**
 * SD implied by a 95% interval of a normal distribution.
 * Returns null when the CI is missing/degenerate (zero-width intervals carry
 * no spread information).
 */
export function sdFromRankCi(ci: unknown): number | null {
  if (!Array.isArray(ci) || ci.length < 2) return null
  const lo = finite(ci[0])
  const hi = finite(ci[1])
  if (lo == null || hi == null) return null
  const sd = Math.abs(hi - lo) / 3.92
  return sd > 0 ? sd : null
}

function axisPercent(rank: number, itemCount: number): number {
  if (itemCount <= 1) return 50
  return ((rank - 1) / (itemCount - 1)) * 100
}

function buildTicks(itemCount: number): RankTick[] {
  if (itemCount < 2) return []
  const budget = effectiveTickBudget(itemCount)
  const step = itemCount <= budget ? 1 : Math.ceil(itemCount / budget)
  const labeledAll = itemCount <= budget
  const ticks: RankTick[] = []
  const seen = new Set<number>()
  const push = (rank: number) => {
    if (seen.has(rank)) return
    seen.add(rank)
    ticks.push({
      offset: axisPercent(rank, itemCount),
      label: labeledAll || rank === 1 || rank === itemCount ? String(rank) : null,
    })
  }
  for (let r = 1; r <= itemCount; r += step) push(r)
  push(itemCount)
  return ticks.sort((a, b) => a.offset - b.offset)
}

/**
 * Build the paint model, or null when there is not enough data to draw
 * (no expected rank, no SD derivable, or fewer than two positions).
 */
export function buildRankRangeBar(input: RankRangeBarInput): RankRangeBarModel | null {
  const n = Math.floor(finite(input.itemCount) ?? 0)
  const mean = finite(input.expectedRank)
  if (n < 2 || mean == null) return null
  const sdRaw = finite(input.rankSd)
  const sd = sdRaw != null && sdRaw >= 0 ? sdRaw : sdFromRankCi(input.rankCi95)
  if (sd == null) return null

  const clampedMean = Math.min(Math.max(mean, 1), n)
  let bandLo = Math.max(1, clampedMean - RANGE_BAR_SD_SPAN * sd)
  let bandHi = Math.min(n, clampedMean + RANGE_BAR_SD_SPAN * sd)
  if (bandHi - bandLo < RANGE_BAR_MIN_SPAN) {
    const half = RANGE_BAR_MIN_SPAN / 2
    bandLo = Math.max(1, clampedMean - half)
    bandHi = Math.min(n, Math.max(bandLo + RANGE_BAR_MIN_SPAN, clampedMean + half))
  }
  const bandSpan = bandHi - bandLo

  const merged = new Map<number, number>()
  merged.set(0, 0)
  merged.set(100, 0)
  const steps = [-1, -2 / 3, -1 / 3, 0, 1 / 3, 2 / 3, 1]
  steps.forEach((step, i) => {
    const rankPos = clampedMean + step * RANGE_BAR_SD_SPAN * sd
    const frac = (rankPos - bandLo) / bandSpan
    if (frac < 0 || frac > 1) return
    const offset = Math.round(frac * 10000) / 100
    const alpha = RANGE_BAR_STOP_ALPHAS[i]
    merged.set(offset, Math.max(merged.get(offset) ?? 0, alpha))
  })
  const stops = [...merged.entries()]
    .map(([offset, alpha]) => ({ offset, alpha }))
    .sort((a, b) => a.offset - b.offset)

  return {
    bandStart: axisPercent(bandLo, n),
    bandEnd: axisPercent(bandHi, n),
    stops,
    ticks: buildTicks(n),
    peakOffset: axisPercent(clampedMean, n),
  }
}

/** CSS background for the painted band from a model's stops. */
export function rankRangeGradient(stops: RankGradientStop[]): string {
  const body = stops
    .map(s => `rgba(var(--pc-primary-rgb), ${s.alpha}) ${s.offset}%`)
    .join(', ')
  return `linear-gradient(90deg, ${body})`
}
