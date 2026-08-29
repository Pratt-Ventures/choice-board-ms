/**
 * Geometry for the factor importance weight range bar.
 *
 * Paints a compact horizontal weight axis (0%…100%) with a color gradient peaking at
 * the posterior mean weight and fading to the background at ±2 SD. Pure math
 * only — WeightRangeBar.vue turns the model into markup.
 */

export interface WeightRangeBarInput {
  weight?: number | null
  weightSd?: number | null
  /** 95% weight interval (0–1); used to approximate SD when weight_sd is missing. */
  weightCi95?: number[] | null
}

export interface WeightGradientStop {
  /** Percent within the painted band (0–100). */
  offset: number
  /** Peak color intensity 0–1 at this stop. */
  alpha: number
}

export interface WeightTick {
  /** Percent across the full axis (0–100). */
  offset: number
  /** Numeric label; null for unlabeled minor ticks. */
  label: string | null
}

export interface WeightRangeBarModel {
  bandStart: number
  bandEnd: number
  stops: WeightGradientStop[]
  ticks: WeightTick[]
  /** Axis percent of the weight peak (0–100). */
  peakOffset: number
}

/** Gradient reaches zero intensity at mean ± this many SDs. */
export const WEIGHT_BAR_SD_SPAN = 2
/** 7 gradient stops: mean, ±⅔ SD, ±4⁄3 SD, ±2 SD. */
export const WEIGHT_BAR_STOP_ALPHAS = [0, 0.15, 0.45, 0.88, 0.45, 0.15, 0]
/** Smallest painted band (in weight units 0–1) so near-certain items stay visible. */
export const WEIGHT_BAR_MIN_SPAN = 0.02

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
export function sdFromWeightCi(ci: unknown): number | null {
  if (!Array.isArray(ci) || ci.length < 2) return null
  const lo = finite(ci[0])
  const hi = finite(ci[1])
  if (lo == null || hi == null) return null
  const sd = Math.abs(hi - lo) / 3.92
  return sd > 0 ? sd : null
}

function axisPercentWeight(weight: number): number {
  return Math.max(0, Math.min(100, weight * 100))
}

function buildWeightTicks(): WeightTick[] {
  const points = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
  return points.map(p => ({
    offset: axisPercentWeight(p),
    label: `${Math.round(p * 100)}%`,
  }))
}

/**
 * Build the paint model, or null when there is not enough data to draw
 * (no weight, no SD derivable).
 */
export function buildWeightRangeBar(input: WeightRangeBarInput): WeightRangeBarModel | null {
  const mean = finite(input.weight)
  if (mean == null) return null
  const sdRaw = finite(input.weightSd)
  const sd = sdRaw != null && sdRaw >= 0 ? sdRaw : sdFromWeightCi(input.weightCi95)
  if (sd == null) return null

  const clampedMean = Math.min(Math.max(mean, 0), 1)
  let bandLo = Math.max(0, clampedMean - WEIGHT_BAR_SD_SPAN * sd)
  let bandHi = Math.min(1, clampedMean + WEIGHT_BAR_SD_SPAN * sd)
  if (bandHi - bandLo < WEIGHT_BAR_MIN_SPAN) {
    const half = WEIGHT_BAR_MIN_SPAN / 2
    bandLo = Math.max(0, clampedMean - half)
    bandHi = Math.min(1, Math.max(bandLo + WEIGHT_BAR_MIN_SPAN, clampedMean + half))
  }
  const bandSpan = bandHi - bandLo
  if (bandSpan <= 0) return null

  const merged = new Map<number, number>()
  merged.set(0, 0)
  merged.set(100, 0)
  const steps = [-1, -2 / 3, -1 / 3, 0, 1 / 3, 2 / 3, 1]
  steps.forEach((step, i) => {
    const wPos = clampedMean + step * WEIGHT_BAR_SD_SPAN * sd
    const frac = (wPos - bandLo) / bandSpan
    if (frac < 0 || frac > 1) return
    const offset = Math.round(frac * 10000) / 100
    const alpha = WEIGHT_BAR_STOP_ALPHAS[i]
    merged.set(offset, Math.max(merged.get(offset) ?? 0, alpha))
  })
  const stops = [...merged.entries()]
    .map(([offset, alpha]) => ({ offset, alpha }))
    .sort((a, b) => a.offset - b.offset)

  return {
    bandStart: axisPercentWeight(bandLo),
    bandEnd: axisPercentWeight(bandHi),
    stops,
    ticks: buildWeightTicks(),
    peakOffset: axisPercentWeight(clampedMean),
  }
}

/** CSS background for the painted band from a model's stops — deep-purple to match factor importance. */
export function weightRangeGradient(stops: WeightGradientStop[]): string {
  const body = stops
    .map(s => `rgba(94, 53, 177, ${s.alpha}) ${s.offset}%`)
    .join(', ')
  return `linear-gradient(90deg, ${body})`
}
