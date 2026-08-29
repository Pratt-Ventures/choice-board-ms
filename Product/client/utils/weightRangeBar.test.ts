import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildWeightRangeBar,
  sdFromWeightCi,
  weightRangeGradient,
} from './weightRangeBar.ts'

test('sdFromWeightCi divides a 95% interval and rejects degenerate CIs', () => {
  assert.ok(Math.abs((sdFromWeightCi([0.1, 0.492]) ?? 0) - 0.1) < 0.001)
  assert.equal(sdFromWeightCi([0.2, 0.2]), null)
  assert.equal(sdFromWeightCi(null), null)
  assert.equal(sdFromWeightCi([0.1]), null)
})

test('buildWeightRangeBar needs weight and derivable SD', () => {
  assert.equal(buildWeightRangeBar({ weight: 0.3, weightCi95: null }), null)
  assert.equal(buildWeightRangeBar({ weight: null, weightCi95: [0.1, 0.3] }), null)
  assert.equal(buildWeightRangeBar({ weight: null, weightCi95: null }), null)
})

test('buildWeightRangeBar places 7 stops fading to zero across the ±2 SD band', () => {
  const m = buildWeightRangeBar({ weight: 0.4, weightSd: 0.1 })
  assert.ok(m)
  // ±2·0.1 = 0.2 around 0.4 → band [0.2, 0.6] → start 20%, end 60%
  assert.ok(Math.abs(m.bandStart - 20) < 0.01)
  assert.ok(Math.abs(m.bandEnd - 60) < 0.01)
  assert.equal(m.stops.length, 7)
  assert.equal(m.stops[0].offset, 0)
  assert.equal(m.stops[0].alpha, 0)
  assert.equal(m.stops[6].offset, 100)
  assert.equal(m.stops[6].alpha, 0)
  const peak = m.stops.find(s => s.offset === 50)
  assert.ok(peak && peak.alpha > 0.8)
  assert.ok(Math.abs(m.peakOffset - 40) < 0.01)
})

test('buildWeightRangeBar clips the band to 0..1', () => {
  const m = buildWeightRangeBar({ weight: 0.95, weightSd: 0.2 })
  assert.ok(m)
  // 0.95 ±0.4 => [0.55,1] clipped
  assert.ok(Math.abs(m.bandStart - 55) < 0.01)
  assert.equal(m.bandEnd, 100)
  assert.equal(m.stops[m.stops.length - 1].alpha, 0)
})

test('buildWeightRangeBar keeps minimal visible band for near-certain weight', () => {
  const m = buildWeightRangeBar({ weight: 0.5, weightSd: 0.001 })
  assert.ok(m)
  const spanPct = m.bandEnd - m.bandStart
  assert.ok(spanPct >= 1.5, `band ${spanPct} should be at least ~2%`)
})

test('buildWeightRangeBar ticks are 0%..100% at 20% steps', () => {
  const m = buildWeightRangeBar({ weight: 0.4, weightSd: 0.05 })
  assert.ok(m)
  assert.deepEqual(m.ticks.map(t => t.label), ['0%', '20%', '40%', '60%', '80%', '100%'])
  assert.deepEqual(m.ticks.map(t => t.offset), [0, 20, 40, 60, 80, 100])
})

test('buildWeightRangeBar falls back to CI-derived SD', () => {
  const m = buildWeightRangeBar({ weight: 0.41, weightCi95: [0.14, 0.73] })
  assert.ok(m, 'CI fallback should render')
})

test('weightRangeGradient emits rgba stops on deep-purple', () => {
  const css = weightRangeGradient([
    { offset: 0, alpha: 0 },
    { offset: 50, alpha: 0.88 },
    { offset: 100, alpha: 0 },
  ])
  assert.match(css, /^linear-gradient\(90deg, /)
  assert.match(css, /rgba\(94, 53, 177, 0\.88\) 50%/)
})
