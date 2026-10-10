import assert from 'node:assert/strict'
import test from 'node:test'
import { CHAT_STORAGE_KEY, LEGACY_CHAT_STORAGE_KEY, loadChats, saveChats, createConversation, withActiveTurns, startConversation, selectConversation, closeConversation } from '../src/lib/chat-storage.ts'
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
    removeItem: (key) => data.delete(key),
  } })
  return data
}
function library(park = 'yose', turns = []) {
  const conversation = { ...createConversation(park), turns }
  return { version: 2, activeId: conversation.id, conversations: [conversation] }
}
const active = (saved) => saved.conversations.find((chat) => chat.id === saved.activeId)
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
  const saved = library('yose', [turn])
  assert.equal(saveChats(saved), true)
  assert.deepEqual(loadChats(), saved)
})
test('interrupted requests restore as stopped without resubmission', (t) => {
  storage(t)
  saveChats(library('yose', [{ id: 'pending', park: 'yose', question: 'Pets?', phase: 'pending', startedAt: 1 }]))
  assert.equal(active(loadChats()).turns[0].phase, 'stopped')
})
test('new chats preserve old messages and switching resumes the chosen chat', (t) => {
  storage(t)
  const first = library('yose', [done()])
  let saved = startConversation(first, active(first).turns, 'yell')
  const secondId = saved.activeId
  assert.notEqual(saved.activeId, first.activeId)
  assert.equal(active(saved).park, 'yell')
  assert.deepEqual(active(saved).turns, [])
  assert.deepEqual(saved.conversations[1], active(first))
  const secondTurn = { id: 'two', park: 'yell', question: 'Bison?', phase: 'stopped' }
  saved = selectConversation(saved, [secondTurn], first.activeId)
  assert.deepEqual(active(saved).turns, [done()])
  saved = withActiveTurns(saved, [...active(saved).turns, { id: 'three', park: 'yose', question: 'Leashes?', phase: 'stopped' }])
  assert.equal(saveChats(saved), true)
  saved = loadChats()
  assert.equal(saved.activeId, first.activeId)
  assert.equal(active(saved).turns.length, 2)
  saved = selectConversation(saved, active(saved).turns, secondId)
  assert.deepEqual(active(saved).turns, [secondTurn])
})
test('leaving a pending chat keeps its question stopped in the original chat', (t) => {
  storage(t)
  const first = library()
  const pending = { id: 'pending', park: 'yose', question: 'Pets?', phase: 'pending', startedAt: 1 }
  const saved = startConversation(first, [pending], 'yose')
  assert.equal(saved.conversations[1].turns[0].phase, 'stopped')
  assert.deepEqual(active(saved).turns, [])
})
test('single-chat history migrates without losing content; legacy is removed only after successful save', (t) => {
  const data = storage(t)
  data.set(LEGACY_CHAT_STORAGE_KEY, JSON.stringify({ version: 1, park: 'yose', turns: [done()] }))
  const saved = loadChats()
  assert.deepEqual(active(saved).turns, [done()])
  assert.equal(data.has(LEGACY_CHAT_STORAGE_KEY), true)
  assert.equal(saveChats(saved), true)
  assert.equal(data.has(LEGACY_CHAT_STORAGE_KEY), false)
  assert.deepEqual(loadChats(), saved)
})
test('corrupt, incompatible and cross-park stored collections fail closed', (t) => {
  const data = storage(t)
  const valid = library('yose', [done()])
  for (const raw of ['{', 'null', JSON.stringify({ ...valid, version: 3 }),
    JSON.stringify({ ...valid, activeId: 'missing' }),
    JSON.stringify({ ...valid, conversations: [active(valid), active(valid)] }),
    JSON.stringify({ ...valid, conversations: [{ ...active(valid), park: 'yell' }] }),
    JSON.stringify({ ...valid, conversations: [{ ...active(valid), turns: [{ ...done(), response: {} }] }] })]) {
    data.set(CHAT_STORAGE_KEY, raw)
    const saved = loadChats()
    assert.equal(saved.conversations.length, 1)
    assert.equal(active(saved).park, null)
    assert.deepEqual(active(saved).turns, [])
  }
})
test('blocked storage and quota errors leave conversation usable', (t) => {
  setWindow(t, { get localStorage() { throw new Error('blocked') } })
  assert.equal(active(loadChats()).park, null)
  assert.equal(saveChats(library('yose', [done()])), false)
  setWindow(t, { localStorage: { setItem() { throw new Error('quota') } } })
  assert.equal(saveChats(library('yose', [done()])), false)
})

test('closing an inactive chat preserves the active reply and persists removal', (t) => {
  storage(t)
  const first = library('yose', [done()])
  const saved = startConversation(first, active(first).turns, 'yell')
  const pending = { id: 'pending', park: 'yell', question: 'Bison?', phase: 'pending', startedAt: 1 }
  const closed = closeConversation(saved, [pending], first.activeId)
  assert.equal(closed.activeId, saved.activeId)
  assert.deepEqual(active(closed).turns, [pending])
  assert.equal(closed.conversations.length, 1)
  assert.equal(saveChats(closed), true)
  assert.equal(loadChats().conversations.some(chat => chat.id === first.activeId), false)
})
test('closing active chat opens a remaining chat with its park and full content', () => {
  const first = library('yose', [done()])
  const saved = startConversation(first, active(first).turns, 'yell')
  const closed = closeConversation(saved, [], saved.activeId)
  assert.equal(closed.activeId, first.activeId)
  assert.deepEqual(active(closed), active(first))
})
test('closing the final chat creates an empty chat for the same park', (t) => {
  storage(t)
  const first = library('yose', [done()])
  const closed = closeConversation(first, active(first).turns, first.activeId)
  assert.notEqual(closed.activeId, first.activeId)
  assert.equal(closed.conversations.length, 1)
  assert.equal(active(closed).park, 'yose')
  assert.deepEqual(active(closed).turns, [])
  saveChats(closed)
  assert.deepEqual(loadChats(), closed)
})
test('closing an unknown chat does not change the collection', () => {
  const saved = library()
  assert.equal(closeConversation(saved, [], 'missing'), saved)
})
