// Run against a Vite preview; all API calls are stubbed and no provider is contacted.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? 'playwright')
import assert from 'node:assert/strict'
const question = { question: 'Old Yosemite question' }
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


const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
 const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
 const errors = []
 page.on('pageerror', error => errors.push(error.message))
 const requests = []
 let releasePending
 const pendingGate = new Promise(resolve => { releasePending = resolve })
 await page.route('**/api/meta', route => route.fulfill({ json: { parks: [], totals: {}, builds: [], active_build: null,
   chat: { ready: true, reason: null }, models: { embedding: {}, generation: {}, reranker: {}, azure_resource: {} },
   runtime: { profile: 'local', budget: {} }, retrieval: {}, local_persistence: {} } }))
 await page.route('**/api/chat', async route => {
  const body = route.request().postDataJSON(); requests.push(body)
  if (body.question === 'Pending old question') await pendingGate
  const response = refusal(); response.question = body.question; response.turn_id = `reply-${requests.length}`
  return route.fulfill({ json: response }).catch(() => {})
 })
 await page.addInitScript(() => {
  if (!localStorage.getItem('parkguide.browser-seeded')) {
   localStorage.setItem('parkguide.browser-seeded', 'yes')
   localStorage.setItem('parkguide.chat.v1', JSON.stringify({ version: 1, park: 'yose', turns: [{ id: 'old', park: 'yose', question: 'Old Yosemite question', phase: 'stopped' }] }))
  }
 })
 await page.goto(process.env.PARKGUIDE_PREVIEW_URL ?? 'http://127.0.0.1:4173')
 await page.getByRole('navigation', { name: 'Saved conversations' }).getByRole('button', { name: 'Old Yosemite question Yosemite' }).waitFor()
 await page.getByRole('button', { name: 'New conversation', exact: true }).click()
 assert.equal(await page.getByRole('dialog').count(), 0)
 const input = page.getByRole('textbox', { name: 'Question about Yosemite' })
 await input.fill('New Yosemite question')
 await page.getByRole('button', { name: 'Send question', exact: true }).click()
 await page.getByText('Please check official information.', { exact: true }).waitFor()
 assert.deepEqual(requests[0].history, [])
 await page.reload()
 await page.getByText('Please check official information.', { exact: true }).waitFor()
 const chats = page.getByRole('navigation', { name: 'Saved conversations' })
 assert.equal(await chats.getByRole('button').count(), 2)
 await chats.getByRole('button', { name: 'Old Yosemite question Yosemite' }).click()
 await page.getByRole('textbox').fill('Old chat follow-up')
 await page.getByRole('button', { name: 'Send question', exact: true }).click()
 await page.getByText('Please check official information.', { exact: true }).waitFor()
 assert.deepEqual(requests[1].history, []) // the original question was stopped, and new chat is excluded
 await chats.getByRole('button', { name: 'New Yosemite question Yosemite' }).click()
 await page.getByRole('textbox').fill('New chat follow-up')
 await page.getByRole('button', { name: 'Send question', exact: true }).click()
 await page.getByText('New chat follow-up', { exact: true }).waitFor()
 await page.waitForFunction(() => JSON.parse(localStorage.getItem('parkguide.chat.v2')).conversations.some(chat => chat.turns.length === 2 && chat.turns[1].phase === 'done'))
 assert.equal(requests[2].history[0].content, 'New Yosemite question')
 assert.equal(requests[2].history.length, 2)
 await page.setViewportSize({ width: 390, height: 844 })
 await page.getByRole('button', { name: 'Open menu' }).click()
 await page.getByRole('navigation', { name: 'Saved conversations' }).getByRole('button', { name: 'Old Yosemite question Yosemite' }).click()
 await page.getByText('Old chat follow-up', { exact: true }).waitFor()
 await page.reload()
 await page.getByText('Old chat follow-up', { exact: true }).waitFor()
 // Leaving a pending reply preserves the question and ignores a late response.
 await page.getByRole('textbox').fill('Pending old question')
 await page.getByRole('button', { name: 'Send question', exact: true }).click()
 await page.getByRole('button', { name: 'Stop waiting' }).waitFor()
 await page.getByRole('button', { name: 'Open menu' }).click()
 await page.getByRole('button', { name: 'New conversation', exact: true }).click()
 await page.getByRole('alertdialog').getByRole('button', { name: 'Continue' }).click()
 releasePending()
 await page.getByRole('heading', { name: 'Ask about visiting Yosemite' }).waitFor()
 const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('parkguide.chat.v2')))
 const archived = saved.conversations.find(chat => chat.turns.some(turn => turn.question === 'Pending old question'))
 assert.equal(archived.turns.at(-1).phase, 'stopped')
 assert.deepEqual(saved.conversations.find(chat => chat.id === saved.activeId).turns, [])
 assert.deepEqual(errors, [])
 console.log('PASS: v1 migration, new chat preservation, reload, chat switching, isolated follow-up context, mobile navigation, pending reply isolation; no browser errors.')
} finally { await browser.close() }
