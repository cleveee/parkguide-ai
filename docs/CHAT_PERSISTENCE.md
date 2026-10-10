# Browser chat persistence

The React web app saves a collection of conversations and the active chat ID per site origin in localStorage under `parkguide.chat.v2`. Reloading restores the selected chat, its park, completed turns, reviewed answers, sources, inspector details, and follow-up context. The existing API history bounds and selected-park filtering still apply. This does not change the legacy Streamlit interface.

New conversation opens an empty chat for the current park and preserves earlier chats. Your chats lists each conversation using its first question and park; select one to reopen and continue it. Changing or clearing the park preserves a chat with messages and opens a separate conversation. In an empty chat, park selection simply changes the park. New conversation is disabled for empty chats to avoid accumulating unused chats.

Each chat has a × close button. Confirmation permanently removes that chat and its messages/evidence from browser storage. Cancel leaves it unchanged. Closing the active chat opens the first remaining saved chat; closing the final chat opens a fresh empty chat for the same park. Closing an inactive chat preserves the active draft, pending reply, and inspector state. Closing an active pending chat aborts browser waiting and ignores late responses.

Leaving a pending reply asks for confirmation, aborts browser waiting and stores its question as stopped; late replies cannot enter another chat. Pending or unsuccessful turns also restore as stopped questions after reload. Requests are never automatically replayed. Composer drafts and evidence/inspector selection reset when moving between chats.

Existing `parkguide.chat.v1` single-chat history migrates automatically into the collection. The legacy copy is removed only after the v2 collection is successfully written. Saved responses pass the same structural validator as network responses before rendering. Invalid JSON, unknown versions, invalid parks, mismatched response parks, duplicate IDs and missing active IDs fall back to an empty collection. Blocked storage or quota failures leave chats usable in memory and show a persistence warning.

Clearing browser site data removes saved chats. Separate browser profiles/devices/origins do not share history. Multiple tabs keep independent in-memory state and the most recent save determines what a subsequent reload restores; live cross-tab synchronization is not implemented.

## Verification — October 10, 2026

- Frontend TypeScript check and production build: passed using existing npm-lockfile dependencies.
- `node --test web/tests/*.test.mjs`: 21 passed, covering API recovery, answer/evidence restoration, multiple chat preservation, switching, active-chat reload, interruption, v1 migration, invalid collections, storage failures, active/inactive/final closure and persisted removal.
- `web/tests/conversations.browser.mjs`: headless Chrome against a local Vite preview with stubbed APIs covers migration, new chat preservation, reload, switching, isolated follow-up context, mobile navigation, pending reply isolation, close cancellation, inactive closing with an active reply/draft, active pending closure, final-chat closure and reload after removal. Run with Playwright available, `node web/tests/conversations.browser.mjs`; optionally set `PLAYWRIGHT_MODULE` to its module location and `PARKGUIDE_PREVIEW_URL` to the preview origin (default port 4173).
- Frontend lint: passed with existing component export warnings.
- No paid model calls or course gold/final-test evaluations were performed. The backend is unchanged by this addition.
