# Web app verification

Verified 2026-10-10T16:00:49.030568+00:00. Claude Code with Opus 5.5 implemented the React/TypeScript frontend and local FastAPI bridge; Codex reviewed the result and exercised the real localhost app.

All 397 offline tests pass (290 existing, 107 API tests), and the final TypeScript/production build passes. A real three-turn conversation delivered two source-reviewed answers and an absent-information refusal using 0, 2 and 4 prior messages. Three recognized local refusals recorded zero Azure calls. Browser checks covered saved source/witness previews, actual retrieval scores/counts/timings, JSON export, corpus filters and pagination, park/reset behavior, cancellation/busy recovery, 375px mobile scrolling and long-word wrapping, reduced motion and responsive modal behavior. No browser console errors were recorded.

The exact measurements, API ledger window, model usage, source hashes and screenshots are in `artifacts/ui/web-app-verification.json`; the dashboard builder includes that record separately from historical Streamlit proof. Component origins and adaptations are in `docs/FRONTEND_REFERENCES.md`.

Human gold review remains 0/40 and the held-out test was unused. These are operational checks, not an accuracy benchmark. Pattern-based preflight can miss alternative wording, stored PDF extraction can contain layout artifacts, and dated sources and AI review cannot guarantee factual correctness. All existing core/config/corpus/gold hashes remain unchanged.
