// All API responses are invented fixtures; no provider is contacted.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? 'playwright')
import assert from 'node:assert/strict'

const questions = ['How long should my pet’s leash be in Yosemite?', 'Which Yosemite paths allow pets?', 'Can pets stay in Yosemite campgrounds?']
const suggestions = questions.map((question, index) => ({ id: `pets-${index}`, question,
  source_url: 'https://www.nps.gov/yose/planyourvisit/pets.htm', supporting_quote: 'Fixture pet rule.', evidence_ids: ['fixture-chunk'] }))
function response(question, history, answer = true) {
 return {
  turn_id: 'fixture', selected_park: 'yose', question, status: answer ? 'answer' : 'refusal',
  text: answer ? 'Fixture pet guidance.' : 'Current conditions are unavailable.', history_content: 'Fixture pet guidance.',
  claims: answer ? [{ number: 1, text: 'Fixture pet guidance.', source_numbers: [1], review: null }] : [],
  sources: answer ? [{ number: 1, title: 'Fixture pets', source_url: suggestions[0].source_url, park: 'yose', page_type: 'html', captured_label: 'Saved fixture', passages: [] }] : [],
  suggested_questions: answer ? suggestions.filter(item => item.question !== question && !history.some(message => message.content === item.question)) : [],
  history: { messages_received: history.length, messages_used: history.length, scope_reset: false }, timing: {}, reason: null,
  inspector: { retrieval: { filters: { parks: ['yose'] }, timings_ms: {}, score_labels: {}, context_ids: [], candidates: [] },
    embedding: {}, generation: {}, review: {}, guard_errors: [], integrity_errors: [], ledger_window: { captured: true, by_kind: {} } },
 }
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
 const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
 const errors = []
 page.on('pageerror', error => errors.push(error.message))
 const requests = []
 let releasePending
 const pending = new Promise(resolve => { releasePending = resolve })
 await page.route('**/api/meta', route => route.fulfill({ json: { parks: [], totals: {}, builds: [], active_build: null,
   chat: { ready: true, reason: null }, models: { embedding: {}, generation: {}, reranker: {}, azure_resource: {} },
   runtime: { profile: 'local', budget: {} }, retrieval: {}, local_persistence: {} } }))
 await page.route('**/api/chat', async route => {
  const body = route.request().postDataJSON()
  requests.push(body)
  if (body.question === 'Need current conditions') await pending
  await route.fulfill({ json: response(body.question, body.history, body.question !== 'Need current conditions') })
 })
 await page.goto(process.env.PARKGUIDE_PREVIEW_URL ?? 'http://127.0.0.1:4173')
 await page.getByRole('button', { name: 'Yosemite', exact: true }).click()
 await page.getByRole('textbox').fill('What are the pet rules?')
 await page.getByRole('button', { name: 'Send question', exact: true }).click()
 const group = page.getByRole('group', { name: 'Suggested follow-up questions' })
 await group.waitFor()
 assert.equal(await group.getByRole('button').count(), 3)
 await group.getByRole('button', { name: questions[0], exact: true }).click()
 assert.equal(await page.getByRole('textbox').inputValue(), questions[0])
 assert.equal(requests.length, 1) // Selecting never automatically makes a paid request.
 await page.getByRole('button', { name: 'Send question', exact: true }).click()
 await page.waitForFunction(() => JSON.parse(localStorage.getItem('parkguide.chat.v2')).conversations[0].turns.at(-1).phase === 'done')
 await group.waitFor()
 assert.equal(await group.getByRole('button').count(), 2)
 assert.equal(requests[1].question, questions[0])
 assert.equal(requests[1].history.length, 2)
 await page.reload()
 await group.waitFor()
 assert.equal(await group.getByRole('button').count(), 2)
 await page.getByRole('button', { name: 'New conversation', exact: true }).click()
 assert.equal(await group.count(), 0)
 const old = page.getByRole('navigation', { name: 'Saved conversations' }).getByRole('button', { name: 'What are the pet rules? Yosemite', exact: true })
 await old.click()
 await group.waitFor()
 await page.setViewportSize({ width: 390, height: 844 })
 await group.getByRole('button', { name: questions[1], exact: true }).click()
 assert.equal(await page.getByRole('textbox').inputValue(), questions[1])
 await page.getByRole('textbox').fill('Need current conditions')
 await page.getByRole('button', { name: 'Send question', exact: true }).click()
 await page.getByRole('button', { name: 'Stop waiting' }).waitFor()
 assert.equal(await group.count(), 0)
 releasePending()
 await page.getByText('Current conditions are unavailable.', { exact: true }).waitFor()
 assert.equal(await group.count(), 0)
 await page.reload()
 await page.getByText('Current conditions are unavailable.', { exact: true }).waitFor()
 assert.equal(await group.count(), 0)
 assert.deepEqual(errors, [])
 console.log('PASS: top-three suggestions, selection without automatic send, context on submit, reload/chat isolation, mobile selection, pending/refusal suppression; no browser errors.')
} finally { await browser.close() }
