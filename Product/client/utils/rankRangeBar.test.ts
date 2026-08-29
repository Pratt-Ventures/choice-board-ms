import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  RANGE_BAR_SD_SPAN,
  buildRankRangeBar,
  rankRangeGradient,
  sdFromRankCi,
} from './rankRangeBar.ts'

test('sdFromRankCi divides a 95% interval and rejects degenerate CIs', () => {
  assert.ok(Math.abs((sdFromRankCi([1, 4.92]) ?? 0) - 1) < 0.001)
  assert.equal(sdFromRankCi([2, 2]), null)
  assert.equal(sdFromRankCi(null), null)
  assert.equal(sdFromRankCi([1]), null)
})

test('buildRankRangeBar needs mean, derivable SD, and at least two positions', () => {
  assert.equal(buildRankRangeBar({ expectedRank: 2, rankSd: null, itemCount: 5 }), null)
  assert.equal(buildRankRangeBar({ expectedRank: 2, rankSd: 0.5, itemCount: 1 }), null)
  assert.equal(buildRankRangeBar({ expectedRank: null, rankSd: 0.5, itemCount: 5 }), null)
  assert.equal(
    buildRankRangeBar({ expectedRank: 2, itemCount: 5 }),
    null,
    'no sd and no CI → not renderable',
  )
})

test('buildRankRangeBar places 7 stops fading to zero across the ±2 SD band', () => {
  const m = buildRankRangeBar({ expectedRank: 3, rankSd: 0.75, itemCount: 9 })
  assert.ok(m)
  // ±2·0.75 = 1.5 ranks around mean 3 → band [1.5, 4.5] of axis 1…9
  assert.ok(Math.abs(m.bandStart - (0.5 / 8) * 100) < 0.01)
  assert.ok(Math.abs(m.bandEnd - (3.5 / 8) * 100) < 0.01)
  assert.equal(m.stops.length, 7)
  assert.equal(m.stops[0].offset, 0)
  assert.equal(m.stops[0].alpha, 0)
  assert.equal(m.stops[6].offset, 100)
  assert.equal(m.stops[6].alpha, 0)
  const peak = m.stops.find(s => s.offset === 50)
  assert.ok(peak && peak.alpha > 0.8)
  // monotone rise then fall
  const alphas = m.stops.map(s => s.alpha)
  for (let i = 1; i < 4; i++) assert.ok(alphas[i] >= alphas[i - 1])
  for (let i = 4; i < alphas.length - 1; i++) assert.ok(alphas[i] >= alphas[i + 1])
  assert.ok(Math.abs(m.peakOffset - ((3 - 1) / 8) * 100) < 0.01)
})

test('buildRankRangeBar clips the band to ranks 1..N', () => {
  const m = buildRankRangeBar({ expectedRank: 1, rankSd: 2, itemCount: 5 })
  assert.ok(m)
  // mean ± 2·2 spans ranks [-3, 9]; clip to the full [1, 5] axis
  assert.equal(m.bandStart, 0)
  assert.equal(m.bandEnd, 100)
  // peak sits at the clipped left edge (rank 1) and fades to zero by rank 5
  assert.equal(m.stops[0].offset, 0)
  assert.equal(m.stops[0].alpha, 0.88)
  assert.equal(m.stops[m.stops.length - 1].offset, 100)
  assert.equal(m.stops[m.stops.length - 1].alpha, 0)
  const alphas = m.stops.map(s => s.alpha)
  for (let i = 1; i < alphas.length; i++) assert.ok(alphas[i] <= alphas[i - 1])
})

test('buildRankRangeBar keeps a minimal visible band for near-certain items', () => {
  const m = buildRankRangeBar({ expectedRank: 1, rankSd: 0.001, itemCount: 6 })
  assert.ok(m)
  const spanPct = m.bandEnd - m.bandStart
  const minPct = (0.2 / 5) * 100
  assert.ok(spanPct >= minPct - 0.01, `band ${spanPct} should be at least ${minPct}`)
})

test('buildRankRangeBar labels every tick (budget = N+1) so 11 and 20 both show all ticks', () => {
  const small = buildRankRangeBar({ expectedRank: 2, rankSd: 0.4, itemCount: 4 })
  assert.ok(small)
  assert.deepEqual(small.ticks.map(t => t.label), ['1', '2', '3', '4'])
  assert.ok(Math.abs(small.ticks[3].offset - 100) < 0.001)

  const eleven = buildRankRangeBar({ expectedRank: 6, rankSd: 1, itemCount: 11 })
  assert.ok(eleven)
  assert.equal(eleven.ticks.length, 11)
  assert.deepEqual(eleven.ticks.map(t => t.label), Array.from({ length: 11 }, (_, i) => String(i + 1)))

  const big = buildRankRangeBar({ expectedRank: 6, rankSd: 1, itemCount: 20 })
  assert.ok(big)
  const labels = big.ticks.filter(t => t.label != null).map(t => t.label)
  assert.deepEqual(labels, Array.from({ length: 20 }, (_, i) => String(i + 1)))
  assert.equal(big.ticks.length, 20)
})

test('buildRankRangeBar falls back to CI-derived SD', () => {
  // ci [1, 4.92] ≈ sd 1 → band [−1, 3] clipped to [1, 3] on a 5-item axis
  const m = buildRankRangeBar({ expectedRank: 2, rankCi95: [1, 4.92], itemCount: 5 })
  assert.ok(m, 'CI fallback should render')
})

test('rankRangeGradient emits rgba stops on the primary token', () => {
  const css = rankRangeGradient([
    { offset: 0, alpha: 0 },
    { offset: 50, alpha: 0.88 },
    { offset: 100, alpha: 0 },
  ])
  assert.match(css, /^linear-gradient\(90deg, /)
  assert.match(css, /rgba\(var\(--pc-primary-rgb\), 0\.88\) 50%/)
})
