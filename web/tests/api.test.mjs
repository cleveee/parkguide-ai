import assert from 'node:assert/strict'
import test from 'node:test'
import { ApiError, getMeta, postChat } from '../src/lib/api.ts'

const question = { selected_park: 'yose', question: 'Where may I walk my dog?', history: [] }

function refusal() {
  return {
    turn_id: 'fixture', selected_park: 'yose', question: question.question,
    status: 'refusal', text: 'Please check official information.', history_content: 'Please check official information.',
    claims: [], sources: [], history: {}, timing: {},
    reason: { code: 'live_information_unavailable', category: 'local_preflight', detail: 'Saved snapshot.' },
    inspector: {
      retrieval: { filters: { parks: ['yose'] }, timings_ms: {}, score_labels: {}, context_ids: [], candidates: [] },
      embedding: {}, generation: {}, review: {}, guard_errors: [], integrity_errors: [],
      ledger_window: { captured: true, by_kind: {} },
    },
  }
}

function abortable(signal) {
  return new Promise((_, reject) => {
    if (signal.aborted) reject(signal.reason)
    else signal.addEventListener('abort', () => reject(signal.reason), { once: true })
  })
}

test('an HTML error page produces a recoverable service message', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<h1>Timeout</h1>', { status: 504 }))
  await assert.rejects(getMeta(), (error) => error instanceof ApiError && error.status === 504 && /temporarily unavailable/.test(error.message))
})

test('invalid successful JSON does not reach the conversation renderer', async (t) => {
  for (const body of ['null', '[]', '<html>upstream error</html>']) {
    t.mock.method(globalThis, 'fetch', async () => new Response(body))
    await assert.rejects(getMeta(), (error) => error.code === 'invalid_response')
  }
})

test('manual stop remains cancellation, not a misleading network failure', async (t) => {
  const controller = new AbortController()
  t.mock.method(globalThis, 'fetch', (_path, { signal }) => abortable(signal))
  const pending = postChat(question, controller.signal)
  const rejected = assert.rejects(pending, (error) => error.name === 'AbortError')
  controller.abort()
  await rejected
})

test('a partial chat object is rejected before React receives it', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ selected_park: 'yose', status: 'answer' }))
  await assert.rejects(postChat(question, new AbortController().signal), (error) => error.code === 'invalid_response')
})

test('partial metadata cannot mark chat ready or crash the park selector', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ chat: { ready: true } }))
  await assert.rejects(getMeta(), (error) => error.code === 'invalid_response')
})

test('a complete refusal can still be shown without sources or paid calls', async (t) => {
  const response = refusal()
  t.mock.method(globalThis, 'fetch', async () => Response.json(response))
  assert.deepEqual(await postChat(question, new AbortController().signal), response)
})

test('malformed nested inspector values do not reach its renderer', async (t) => {
  for (const mutate of [
    (value) => { delete value.reason.category },
    (value) => { value.inspector.ledger_window.by_kind.generation = null },
  ]) {
    const response = refusal()
    mutate(response)
    t.mock.method(globalThis, 'fetch', async () => Response.json(response))
    await assert.rejects(postChat(question, new AbortController().signal), (error) => error.code === 'invalid_response')
  }
})

test('a stalled chat times out once without silently resending the paid request', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const fetch = t.mock.method(globalThis, 'fetch', (_path, { signal }) => abortable(signal))
  const pending = postChat(question, new AbortController().signal)
  const rejected = assert.rejects(pending, (error) => error.code === 'request_timeout' && /may still/.test(error.message))
  t.mock.timers.tick(110_000)
  await rejected
  assert.equal(fetch.mock.callCount(), 1)
})

test('the deadline also covers a response body that never finishes', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  t.mock.method(globalThis, 'fetch', async (_path, { signal }) => ({ ok: true, status: 200, json: () => abortable(signal) }))
  const pending = getMeta()
  const rejected = assert.rejects(pending, (error) => error.code === 'request_timeout')
  await Promise.resolve()
  t.mock.timers.tick(20_000)
  await rejected
})

test('structured server failures retain their reason and usage record', async (t) => {
  const details = { ledger_window: { captured: false, reason: 'unavailable' } }
  t.mock.method(globalThis, 'fetch', async () => Response.json({ error: { code: 'busy', message: 'Try again shortly.', details } }, { status: 409 }))
  await assert.rejects(getMeta(), (error) => error.code === 'busy' && error.status === 409 && error.details.ledger_window.captured === false)
})

function supportedSuggestion() {
  return { id: 'pets-leash', question: 'How long should my pet’s leash be in Yosemite?',
    source_url: 'https://www.nps.gov/yose/planyourvisit/pets.htm', supporting_quote: 'Keep pets on a six-foot leash.', evidence_ids: ['saved-chunk'] }
}

test('supported follow-ups are accepted on answers and old responses still work', async (t) => {
  const response = refusal()
  response.status = 'answer'
  response.suggested_questions = [supportedSuggestion()]
  t.mock.method(globalThis, 'fetch', async () => Response.json(response))
  assert.deepEqual((await postChat(question, new AbortController().signal)).suggested_questions, response.suggested_questions)
})

test('unbounded, unsupported, duplicate and foreign-park suggestions fail closed', async (t) => {
  for (const mutate of [
    value => { value.suggested_questions = Array.from({ length: 4 }, () => supportedSuggestion()) },
    value => { value.suggested_questions[0].evidence_ids = [] },
    value => { value.suggested_questions[0].supporting_quote = '' },
    value => { value.suggested_questions[0].source_url = 'https://www.nps.gov/yell/planyourvisit/pets.htm' },
    value => { value.suggested_questions.push(supportedSuggestion()) },
    value => { value.status = 'refusal' },
  ]) {
    const response = refusal()
    response.status = 'answer'
    response.suggested_questions = [supportedSuggestion()]
    mutate(response)
    t.mock.method(globalThis, 'fetch', async () => Response.json(response))
    await assert.rejects(postChat(question, new AbortController().signal), error => error.code === 'invalid_response')
  }
})
