# Browser chat persistence

The React web app saves one active conversation per site origin in localStorage under `parkguide.chat.v1`. Reloading restores the selected park, completed turns, reviewed answers, sources, inspector details, and follow-up context. The existing API history bounds and selected-park filtering still apply. This does not change the legacy Streamlit interface.

Pending or unsuccessful turns restore as stopped questions; requests are never automatically replayed. New conversation and confirmed park changes replace the saved conversation. Clearing browser site data removes it. Separate browser profiles/devices/origins do not share history. Multiple tabs keep independent in-memory state and the most recent save determines what a subsequent reload restores; live cross-tab synchronization is not implemented.

Saved responses pass the same structural validator as network responses before rendering. Invalid JSON, unknown versions, invalid parks, mismatched response parks and duplicate IDs fall back to an empty conversation. Blocked storage or quota failures leave the current chat usable and show a persistence warning.

## Verification — October 10, 2026

- Frontend TypeScript check and production build: passed using the npm lockfile.
- `node --test web/tests/*.test.mjs`: 15 passed, covering API recovery, reload restoration, pending interruption, resetting/changing parks, invalid saved data and storage failures.
- Frontend lint: passed with existing component export warnings.
- Python syntax check for the metadata wording change: passed.
- Backend pytest suites could not run on this machine because neither available Python runtime has pytest installed. No paid model calls or course gold/final-test evaluations were performed.
