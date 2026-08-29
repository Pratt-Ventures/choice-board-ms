import { test } from 'node:test'
import assert from 'node:assert/strict'
import { quotaCopy } from './submissionQuota.ts'

test('quotaCopy is empty when counts are missing', () => {
  assert.equal(quotaCopy(), '')
  assert.equal(quotaCopy(1), '')
  assert.equal(quotaCopy(undefined, 10), '')
  assert.equal(quotaCopy(0, 10), '')
})

test('quotaCopy stays hidden at or below one-third of the daily cap', () => {
  assert.equal(quotaCopy(1, 10), '')
  assert.equal(quotaCopy(3, 10), '')
  assert.equal(quotaCopy(1, 3), '')
  assert.equal(quotaCopy(3, 9), '')
})

test('quotaCopy appears after one-third of the daily cap', () => {
  const n10 = quotaCopy(4, 10)
  assert.match(n10, /We limit submissions in a 24 hour period due to our capacity/)
  assert.match(n10, /You have submitted 4 of 10 as of now/)
  assert.equal(
    quotaCopy(4, 9),
    'We limit submissions in a 24 hour period due to our capacity. You have submitted 4 of 9 as of now.',
  )
  assert.equal(
    quotaCopy(2, 3),
    'We limit submissions in a 24 hour period due to our capacity. You have submitted 2 of 3 as of now.',
  )
})

test('quotaCopy shows at the cap and past it', () => {
  assert.equal(
    quotaCopy(10, 10),
    'We limit submissions in a 24 hour period due to our capacity. You have submitted 10 of 10 as of now.',
  )
  assert.equal(
    quotaCopy(11, 10),
    'We limit submissions in a 24 hour period due to our capacity. You have submitted 11 of 10 as of now.',
  )
})
