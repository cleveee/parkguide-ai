# Selected park and source-only answers

Choose one park in the main **Park** selector: Yosemite, Yellowstone or Grand Canyon. It starts empty and chat is disabled until a park is selected. A visible **Selected park** banner and park-specific input placeholder keep the scope clear. Changing or clearing the selector discards the conversation; **New conversation** resets history within the selected park. Optional search/reranking controls remain collapsed in the sidebar.

The UI always passes `selected_park` into the shared chat service. Invalid park codes and selected-park closed-book requests fail before provider calls. The service overwrites inferred park filters, adds only the selected name to the search question if needed, and supplies an explicit park constraint to generation and review. A prompt naming another supported park refuses locally; it cannot change the selector. Foreign-park exchanges are excluded from service history while earlier selected-park context is retained.

Retrieval is restricted to saved, active-build chunks belonging to that park. The selected-park default now uses the existing local reranker: measured scoped hybrid search sometimes buried the relevant safety passage beneath generic park text. The legacy unselected diagnostic default remains hybrid without reranking. Optional controls allow the local ablation; unsupported evidence still refuses with either setting.

Before generation, every candidate, reranked passage and final passage must have nonempty saved text/ID and an approved official NPS visitor URL for the selected park. Foreign, empty or conflicting passage identities lead to a refusal. Empty retrieval never falls back to model memory or earlier assistant answers. The SQLite corpus and original evaluation data are unchanged.

Every factual answer requires a complete source review. Each retained claim needs citations, an affirmative review decision, and bounded exact source-text witnesses for every cited ID. Mechanical guards also check citation identity, numbers and quotation limits. Wrong-park claims are withheld even if the AI reviewer approves them. Missing, failed, malformed or unsupported review withholds factual output. Malformed generated answers, including answers with no claims, become controlled refusals with safe error/usage metadata. For nonanswers, controlled messages replace free-form model prose, preventing invented facts or URLs from being smuggled through a refusal or clarification. Available raw attempted output remains in the trace.

The saved public-source database cannot verify live conditions, future opening status or personal reservation records. Recognized live/future-status and private-record lookups refuse before embedding/generation and give a relevant next step. A static rule question that merely mentions visiting today can still use the saved sources. Corpus-absent or insufficiently retrieved facts must refuse through the source-only generation/review path. A source gap does not prove that the real-world place or fact does not exist.

Exact witnesses prove that text exists in the selected source; AI review still decides whether the claim follows from that text and answers the question. The system can incorrectly accept a paraphrase or withhold a supported answer. This update does not establish a zero-hallucination guarantee, human accuracy, or current validity of old source dates. Official source links open today's page; saved excerpts describe the snapshot used.

The legacy CLI/evaluation mode with `selected_park=None` retains historical cross-park diagnostics. Closed-book B0 is confined to that diagnostic contract. It is unavailable through the selected-park UI.

## Verification record

`scripts/check_park_scope.py` runs new non-gold cases through actual database retrieval, Azure query embeddings and Luna generation/review on the same existing resource. It preserves six three-turn dialogues and three singleton missing-fact checks per run, including actual preceding assistant messages. Every attempt, expected action, boundary check, error, code/config/corpus hash and priced API usage is saved under `artifacts/park-scope/`. Operational matches are not semantic accuracy or human review. Follow-up manifests link the preceding measured run; failures are never overwritten.

The original seven stages, 305 attempted rows and 66 provisional AI labels remain unchanged. The new scoped checks are reported separately in the [HTML dashboard](../dashboard/index.html). Live selector/scope/source-card evidence is in `artifacts/ui/park-scope-verification.json` and `park-selector-preview.png`; the independent offline review is `artifacts/ui/park-scope-review.md`.

Reproduce another paid non-gold run within the existing budget:

```sh
.venv/bin/python scripts/check_park_scope.py
```

The 40 human review pending gold drafts and held-out test remain outside this update.
