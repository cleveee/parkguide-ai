# Suggested follow-up questions

After the latest delivered answer, Explore next offers up to three relevant questions for the selected park. Choosing one fills the composer and focuses it; the visitor can edit it and press Send. Suggestions are hidden while a reply is pending and after refusals or clarification requests. They are saved with each answer, so reopening a conversation or reloading restores its latest suggestions. Older saved responses without suggestions remain compatible.

## Grounding and relevance

`config/followup_questions.json` contains 42 curated source-grounded questions, 14 per park. Each narrow, self-contained question names its park and includes an exact supporting quote, official saved source URL, topic and relevance keywords. Topics include pets, camping, food storage, wildlife, hiking safety, transport and entrance passes; coverage varies with the saved corpus. This is a curated catalog, not unrestricted generated questions.

The server checks each eligible entry against a selected-park chunk in the active database build, validates its document URL/hash against that build's snapshot, and requires the exact quote in a bounded supporting chunk. Missing, stale, oversized or foreign-park support is omitted. Keywords determine relevance, not answerability. Suggestions rank by topic overlap with the current question/reviewed answer and shared cited source, with stable IDs breaking ties. Already asked questions and close wording matches are excluded. If fewer than three relevant supported questions exist, fewer are displayed; unrelated defaults are never added.

## Answering a suggestion

On submission the server matches the question to the catalog and rechecks its support. It reloads the supporting chunk from SQLite into the shared answer path; the browser cannot submit passage text or retrieval overrides. The question is standalone, so it does not inherit a previous table URL or a dialogue planner's alternate subject. The inspector marks this retrieval mode as `suggested_followup` and does not claim reranking occurred. Edited/noncatalog questions use normal retrieval.

Answers still use the approved generator, source review, citation integrity checks, selected-park guards and budget limits. Stored support establishes that the question is answerable from the corpus; it does not guarantee a model/service call will succeed or certify answer accuracy. Failures still fail closed. Suggestions add no model calls; submitting a question uses the normal paid answer/source-review calls. No corpus, vectors, evaluation gold or frozen test data was changed.

## Verification — October 10, 2026

- Full offline Python regression suite: 591 passed using pinned serving dependencies in an isolated Python 3.12 environment.
- Every catalog quote is an exact substring of an active selected-park chunk. All 42 questions were routed through the shared answer/review path using invented offline generator/reviewer fixtures; these checks validate passage routing and mechanical contracts, not model accuracy or human semantic review.
- API tests cover supported suggestions, submitting a catalog question with its supporting evidence, suppression on nonanswers, and rejection of browser retrieval overrides.
- Frontend Node tests: 23 passed, including optional old-response compatibility, maximum-three bounds, duplicate/foreign-park/missing-support validation and persistence.
- TypeScript check, production build and lint passed (existing component-export and bundle-size warnings remain).
- Headless Chrome with stubbed APIs passed suggestion selection, send/context behavior, reload/chat isolation, mobile selection and pending/refusal suppression; existing saved-chat/close-chat browser regressions also passed.
- No live provider calls or course final-test evaluations were performed.

Browser checks: run a Vite preview on port 4173, then `node web/tests/followups.browser.mjs` with Playwright/Chrome available. `PLAYWRIGHT_MODULE` and `PARKGUIDE_PREVIEW_URL` can select a module location and preview origin.
