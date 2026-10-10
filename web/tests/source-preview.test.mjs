import assert from 'node:assert/strict'
import test from 'node:test'
import { findWitnessMatches, pageWitnesses } from '../src/lib/source-preview.ts'

test('evidence spans inline markup and whitespace without changing the words', () => {
  const result = findWitnessMatches([{ text: 'Dogs are ' }, { text: 'not\n allowed' }, { text: ' on trails.' }], ['Dogs are not allowed on trails.'])
  assert.deepEqual(result.counts, [1])
  assert.equal(result.highlights.length, 3)
})

test('unrelated blocks do not create false joined words', () => {
  assert.deepEqual(findWitnessMatches([{ text: 'Dog' }, { text: 's', breakBefore: true }], ['Dogs']).counts, [0])
})

test('missing quotes stay missing, and repeated/overlapping evidence is counted', () => {
  const result = findWitnessMatches([{ text: 'No dogs. No dogs.' }], ['No dogs.', 'dogs', 'Cats allowed'])
  assert.deepEqual(result.counts, [2, 2, 0])
  assert.equal(result.highlights.length, 4)
})

test('page quotes keep all claims when one quote supports multiple statements', () => {
  const page = { passages: [{ reviewer_witnesses: [{ quote: '6 feet', claim_number: 2 }, { quote: '6 feet', claim_number: 1 }, { quote: '  ', claim_number: 3 }] }] }
  assert.deepEqual(pageWitnesses(page), [{ quote: '6 feet', claims: [1, 2] }])
})
