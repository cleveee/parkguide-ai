# Modal-stack fix (Claude Code, claude-opus-5-5)

Date: 2026-10-10. Input: `artifacts/frontend/final-browser-findings.md`. Only `web/src/App.tsx` changed. No core/API/config/data/legacy changes, no paid calls, no servers, no Git, no credential or evaluation reads.

## Cause

The responsive Inspector Sheet's `open` prop was `view === "chat" && !desktop && inspectorOpen`. Resizing from 1280 px to 375 px while the EvidenceDialog was open therefore mounted the sheet as a second Radix modal layer. Because it mounted later, it became the top dismissable layer even though it was visually under the evidence dialog. The first Escape went to the sheet, whose `onOpenChange={setInspectorOpen}` cleared `inspectorOpen`; only a second Escape reached the evidence dialog. The mobile Menu sheet had the same exposure, since its `open` was just `menuOpen`.

## Change (`web/src/App.tsx`)

- New derived values:
  - `evidenceShown`: an evidence target that resolves to a real source page.
  - `dialogShown = evidenceShown || aboutOpen || Boolean(confirm)`.
  - `menuSheetShown = menuOpen && !wide && !dialogShown`, where `wide` is `(min-width: 768px)`, matching the `md` breakpoint at which the sidebar is visible and the menu button is hidden.
  - `inspectorSheetShown = view === "chat" && !desktop && inspectorOpen && !dialogShown && !menuSheetShown`.
- Both sheets now use these derived `open` values. Their `onOpenChange` handlers change state only for a dismissal of the sheet that is actually shown (`if (!open && inspectorSheetShown) setInspectorOpen(false)`, and likewise for the menu). A breakpoint change or another dialog therefore never clobbers `inspectorOpen` or `menuOpen`.
- `request()` closes the mobile menu before opening the conversation-confirm AlertDialog, so the confirmation is the single modal layer. Cancelling leaves the menu closed.
- Unchanged:
  - Chat turns, park, evidence target, inspector turn selection, and `inspectorOpen` (the desktop side panel resumes when the window is widened again; the sheet appears once the other dialog closes at narrow widths).
  - Inspect actions, park-switch resets and source evidence.
  - The desktop side panel, which is not modal.

## Expected behavior for the root recheck

1. At 1280 px: open the Inspector, then a citation's EvidenceDialog. Resize to 375 px: no sheet mounts while evidence is open. Resize back to 1280 px and press Escape once: the evidence dialog closes, and the inspector panel is still open.
2. Same steps, but close the evidence at 375 px: the Inspector Sheet then appears as the only layer (`inspectorOpen` was preserved). One Escape closes it.
3. The menu sheet never shows together with How it works, evidence or a confirmation, and it is hidden at ≥768 px.

## Checks

| Command | Result |
|---|---|
| `npm --prefix web run build` (`tsc -b && vite build`) | Passed. JS 606.72 kB (187.43 kB gzip), CSS 81.41 kB; the existing >500 kB chunk warning remains |
| `npm --prefix web run lint` | 0 errors; nothing beyond the 11 known `only-export-components` notices |

Python tests were not rerun, as instructed: no Python file changed. Browser behavior is not verified by me; the root rechecks the scenario above. The rebuilt `web/dist` is served from disk, so a browser reload picks it up without a server restart.
