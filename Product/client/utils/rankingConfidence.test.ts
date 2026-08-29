import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  computeRankingConfidence,
  confidenceLevelFromValue,
  emptyRankingConfidence,
  interpolateConfidenceColor,
  mergeLiveEvidence,
  type RankingEvidenceGroup,
} from './rankingConfidence.ts'

function winner(a: number, b: number) {
  return {
    item_a_id: a,
    item_b_id: b,
    winner_id: a,
    loser_id: b,
    response: 'winner',
    presented_left_id: a,
    presented_right_id: b,
  }
}

function unsure(a: number, b: number) {
  return {
    item_a_id: a,
    item_b_id: b,
    winner_id: a,
    loser_id: b,
    response: 'unsure',
    presented_left_id: a,
    presented_right_id: b,
  }
}

function optionGroup(pairings: Array<Record<string, unknown>>, extra: Partial<RankingEvidenceGroup> = {}): RankingEvidenceGroup {
  return {
    group_type: 'alternative',
    criterion_id: null,
    pass_index: 1,
    item_ids: [1, 2, 3],
    question_budget: 3,
    ranking_target: 'full',
    pairings,
    ...extra,
  }
}

test('empty evidence is None', () => {
  const empty = computeRankingConfidence({})
  assert.equal(empty.level, 'none')
  assert.equal(empty.value, 0)
  assert.equal(empty.label, 'None')
  assert.deepEqual(emptyRankingConfidence().level, 'none')
})

test('six-level boundaries', () => {
  assert.equal(confidenceLevelFromValue(0), 'none')
  assert.equal(confidenceLevelFromValue(0.01), 'low')
  assert.equal(confidenceLevelFromValue(0.2), 'low')
  assert.equal(confidenceLevelFromValue(0.21), 'moderate')
  assert.equal(confidenceLevelFromValue(0.4), 'moderate')
  assert.equal(confidenceLevelFromValue(0.41), 'fair')
  assert.equal(confidenceLevelFromValue(0.6), 'fair')
  assert.equal(confidenceLevelFromValue(0.61), 'good')
  assert.equal(confidenceLevelFromValue(0.8), 'good')
  assert.equal(confidenceLevelFromValue(0.81), 'strong')
  assert.equal(confidenceLevelFromValue(1), 'strong')
})

test('unsure does not inflate coverage', () => {
  const decisive = computeRankingConfidence({
    optionIds: [1, 2, 3],
    evidence: [optionGroup([winner(1, 2), winner(1, 3)])],
  })
  const withUnsure = computeRankingConfidence({
    optionIds: [1, 2, 3],
    evidence: [optionGroup([winner(1, 2), winner(1, 3), unsure(2, 3)])],
  })
  assert.equal(withUnsure.value, decisive.value)
})

test('undo drops the score', () => {
  const two = computeRankingConfidence({
    optionIds: [1, 2, 3],
    evidence: [optionGroup([winner(1, 2), winner(1, 3)])],
  })
  const one = computeRankingConfidence({
    optionIds: [1, 2, 3],
    evidence: [optionGroup([winner(1, 2)])],
  })
  assert.ok(two.value > one.value)
})

test('missing factor ranking keeps multi-factor below Strong', () => {
  const optionsOnly = computeRankingConfidence({
    optionIds: [1, 2, 3],
    evidence: [optionGroup([winner(1, 2), winner(1, 3), winner(2, 3)])],
  })
  const multiMissingFactors = computeRankingConfidence({
    optionIds: [1, 2, 3],
    factorIds: [10, 11],
    evidence: [optionGroup([winner(1, 2), winner(1, 3), winner(2, 3)], { criterion_id: 10 })],
  })
  assert.ok(optionsOnly.value > multiMissingFactors.value)
  assert.notEqual(multiMissingFactors.level, 'strong')
})

test('color interpolates danger toward success', () => {
  const low = interpolateConfidenceColor(0)
  const mid = interpolateConfidenceColor(0.5)
  const high = interpolateConfidenceColor(1)
  assert.match(low, /--pc-danger/)
  assert.match(mid, /--pc-warning/)
  assert.match(high, /--pc-success/)
  assert.equal(computeRankingConfidence({}).color, low)
})

test('live overlay replaces the current group and undo follows pairings', () => {
  const seeded: RankingEvidenceGroup[] = [optionGroup([winner(1, 2)], { client_group_id: 'g1' })]
  const live: RankingEvidenceGroup = optionGroup([winner(1, 2), winner(1, 3)], { client_group_id: 'g1' })
  const merged = mergeLiveEvidence(seeded, live)
  assert.equal(merged.length, 1)
  assert.equal((merged[0].pairings || []).length, 2)
  const undone = mergeLiveEvidence(merged, optionGroup([winner(1, 2)], { client_group_id: 'g1' }))
  const withLive = computeRankingConfidence({ optionIds: [1, 2, 3], evidence: merged })
  const afterUndo = computeRankingConfidence({ optionIds: [1, 2, 3], evidence: undone })
  assert.ok(withLive.value > afterUndo.value)
})
