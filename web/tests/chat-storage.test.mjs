import assert from 'node:assert/strict'
import test from 'node:test'
import { CHAT_STORAGE_KEY, loadChat, saveChat } from '../src/lib/chat-storage.ts'
function setWindow(t, value) {
  globalThis.window = value
  t.after(() => { delete globalThis.window })
}
const question = { question: 'Where may I walk my dog?' }
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


function storage(t) {
  const data = new Map()
  setWindow(t, { localStorage: {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
  } })
  return data
}
const done = () => ({ id: 'one', park: 'yose', question: question.question, phase: 'done', response: refusal(), clientMs: 12 })

test('reload restores park, full answer, evidence and follow-up content', (t) => {
  storage(t)
  const turn = done()
  turn.response.status = 'answer'
  turn.response.reason = null
  turn.response.claims = [{ number: 1, text: 'Keep pets on a leash.', source_numbers: [1], review: null }]
  turn.response.sources = [{ number: 1, title: 'Pets', source_url: 'https://www.nps.gov/yose/planyourvisit/pets.htm', park: 'yose',
    page_type: 'html', effective_date: null, crawled_at: null, captured_label: 'Saved snapshot',
    passages: [{ chunk_id: 'chunk', doc_id: 'doc', heading_path: 'Pets', excerpt: 'Keep pets on a leash.',
      excerpt_leading_omission: false, excerpt_truncated: false, saved_text: 'Keep pets on a leash.', pdf_start_page: null,
      passage_url: 'https://www.nps.gov/yose/planyourvisit/pets.htm', source_spans: [{ start: 0, end: 21, kind: 'paragraph' }],
      claim_numbers: [1], reviewer_witnesses: [{ claim_number: 1, quote: 'Keep pets on a leash.' }] }] }]
  turn.response.history_content = 'Keep pets on a leash. [Pets](https://www.nps.gov/yose/planyourvisit/pets.htm)'
  assert.equal(saveChat('yose', [turn]), true)
  assert.deepEqual(loadChat(), { version: 1, park: 'yose', turns: [turn] })
})
test('interrupted requests restore as stopped without resubmission', (t) => {
  storage(t)
  saveChat('yose', [{ id: 'pending', park: 'yose', question: 'Pets?', phase: 'pending', startedAt: 1 }])
  assert.equal(loadChat().turns[0].phase, 'stopped')
})
test('new conversation and park change replace persisted history', (t) => {
  storage(t)
  saveChat('yose', [done()])
  saveChat('yose', [])
  assert.deepEqual(loadChat().turns, [])
  saveChat('yell', [])
  assert.equal(loadChat().park, 'yell')
  saveChat(null, [])
  assert.equal(loadChat().park, null)
})
test('corrupt, incompatible and cross-park stored data fail closed', (t) => {
  const data = storage(t)
  for (const raw of ['{', 'null', JSON.stringify({ version: 2, park: 'yose', turns: [] }),
    JSON.stringify({ version: 1, park: 'fake', turns: [] }),
    JSON.stringify({ version: 1, park: 'yell', turns: [done()] }),
    JSON.stringify({ version: 1, park: 'yose', turns: [{ ...done(), response: {} }] })]) {
    data.set(CHAT_STORAGE_KEY, raw)
    assert.deepEqual(loadChat(), { version: 1, park: null, turns: [] })
  }
})
test('blocked storage and quota errors leave conversation usable', (t) => {
  setWindow(t, { get localStorage() { throw new Error('blocked') } })
  assert.equal(loadChat().park, null)
  assert.equal(saveChat('yose', [done()]), false)
  setWindow(t, { localStorage: { setItem() { throw new Error('quota') } } })
  assert.equal(saveChat('yose', [done()]), false)
})
