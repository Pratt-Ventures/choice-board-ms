import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  factorDetailsCopy,
  hasCustomComparisonQuestion,
  optionCompareQuestion,
  optionCompareTitle,
  trimmedComparisonQuestion,
} from './comparePrompt.ts'

test('trimmed comparison question treats blank as absent', () => {
  assert.equal(trimmedComparisonQuestion(null), null)
  assert.equal(trimmedComparisonQuestion('   '), null)
  assert.equal(trimmedComparisonQuestion('Which option has lower Engineering Cost?'), 'Which option has lower Engineering Cost?')
})

test('option frames use custom question or live fallback', () => {
  assert.equal(optionCompareQuestion({ comparison_question: 'Which is cheaper?' }), 'Which is cheaper?')
  assert.equal(optionCompareQuestion({ title: 'Cost' }), 'Which option is better?')
  assert.equal(hasCustomComparisonQuestion({ comparison_question: '  ' }), false)
  assert.equal(optionCompareTitle({ title: 'Engineering Cost' }, 10), 'Engineering Cost')
  assert.equal(optionCompareTitle(null, null), 'Overall')
})

test('factor details omit empty description', () => {
  assert.deepEqual(
    factorDetailsCopy({ title: 'Cost', description: '  ' }, 10),
    { title: 'Cost', description: '' },
  )
})
