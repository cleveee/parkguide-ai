# Independent selected-park review

Refreshed at 2026-10-10T14:37:43Z after migration to shared Azure credentials, pinned GPT-6 Luna generation/review, safe rate-limit handling, and removal of uncited passages from reviewer inputs. Scope: integrated `app.py`, `src/parkguide/chat.py`, `src/parkguide/generation.py`, `src/parkguide/claim_review.py`, and `config/project.json`; five offline regression files listed below. This review used no provider requests, sealed/gold content, browser interaction, production writes, or real budget-ledger mutations. HTTP behavior was exercised through `httpx.MockTransport`, which cannot access the network.

## Result

No unresolved blocking omission found in the implemented UI, source-scope, and Azure provider boundaries. The targeted command `.venv/bin/python -m pytest -q tests/test_generation.py tests/test_azure_contract.py tests/test_park_scope.py tests/test_claim_review.py tests/test_retry.py` passed **202 tests in 0.81 seconds**, including the unchanged **69 selected-park cases**. These are offline contract tests, not a measured semantic benchmark or a live UI result.

Verified boundaries:

- The selector starts empty, disables chat until a supported park is chosen, clearly labels the selected park, and clears the conversation when the selection changes.
- The UI supplies `selected_park` to the shared answer path. That path rejects invalid selections and selected-park closed-book requests, replaces inferred park filters, and carries the selected name into retrieval and generation.
- Explicit other supported parks refuse before embedding, retrieval, or generation. Foreign-park history is cleared without mutating the caller's history.
- Approved-path/host checks cover candidates, reranked passages, and final contexts. Empty/whitespace text, foreign final passages absent from candidates, and conflicting duplicate passage identities fail before generation.
- Empty evidence never falls back to a previous assistant answer or a generator-only factual answer.
- Selected-park factual output requires a complete reviewed decision for each claim, exact bounded witnesses for every cited passage, correct indexing, and mechanical citation/numerical checks. Missing, malformed, reordered, unsupported, or failed review cases were exercised.
- A reviewer-approved claim naming a different supported park is still withheld by the deterministic park check.
- Free-form `refuse` and `clarify` output cannot smuggle an invented fact or URL into the delivered response. The original payload remains in `raw_response`; the rendered response uses controlled text.
- The shorter park-name retrieval prefix changes query wording only. The single-park metadata filter, selected-park generation instruction, mandatory review, and final claim scope check remain intact.
- Failed provider reviews retain only a fixed validation reason and clipped review fields from parsed JSON: at most eight decisions, eight witnesses per decision, and a shared 4,096-character text budget. Provider exception bodies and headers are not copied into these diagnostics. This diagnostic branch does not turn a failed review into delivered factual output.
- Finite rejected generation responses, including `answer_without_claims`, become controlled selected-park source-gap refusals and retain a safe error code/usage. They do not trigger semantic review or subsequent table derivation. The unselected diagnostic path still raises its rejected generation error. Provider-401, credential/configuration drift, and unknown provider-usage failures continue to raise rather than being disguised as source absence.
- The real `Generator` wrapper was exercised with a fake SDK client and fake `Budget`: a malformed response carrying 30 input/20 output tokens settled exactly once with `error=True`, retained the synthetic usage/cost, and closed the fake client. No real ledger or provider was touched.
- The selected UI/service now defaults to the existing local reranker, while unselected diagnostics retain `default_rerank=false`. Fake-retriever tests verify both defaults and confirm a foreign passage appearing only in the reranked list still fails before generation.
- Reviewer wire output now contains short `witness_id` references only. The adapter resolves each ID to a fixed mechanically extracted source/quote pair, rejects invented/duplicate IDs, and applies the same claim-owned citation, exact-substring, bounded-word, completeness, and index checks. Changing serialization does not permit model-written quotation text to become a source witness.
- Reviewer inputs and the witness catalog contain only the union of passages actually cited by the claims. Invented uncited legends, unrelated facts, injection instructions, URLs, titles, and metadata were placed before, between, and after cited passages; none reached the fake provider payload or schema. All cited text and allowed metadata remained exact, the input list remained unchanged, and witnesses were renumbered from the cited subset.
- Filtering cannot hide malformed original passage text/IDs or conflicting uncited duplicate IDs: those fail before a provider call. The shared pure validator also rejects those original inputs. Within the cited union, a witness belonging only to another claim still fails `witness_id_not_cited`; the chat path revalidates decisions against its actual contexts.
- Generation and review use the existing embedding resource's canonical endpoint and the same `AZURE_OPENAI_API_KEY`; the generation deployment is a separate explicit alias. Direct OpenAI, extra accepted model versions, resource/deployment drift, and separate generation endpoint/key variables are rejected. The accepted text model is pinned to `gpt-6-luna-2026-09-22`.
- Generation and review share the same request helper and verified configuration: `temperature=0`, `reasoning_effort=none`, `max_completion_tokens=1000`, strict JSON schemas, and `store=false`. SDK retries are disabled. A simulated HTTP 302 exercised the real SDK/HTTP client and produced one request to the configured Azure host; no request reached the redirect target.
- API failures retain only allowlisted provider error codes and finite numeric retry delays; raw provider messages, credentials, and header strings are suppressed. Seconds and millisecond hints are handled, and finite hints above 3,600 seconds are capped rather than discarded so they cannot become an early retry.
- Generation and review honor the same delay policy: zero hints wait at least one second; 429 without a usable hint waits 60 seconds; hints above 60 seconds stop without a retry; transient server errors back off; credential failures never retry. The tests replace sleep with a mock and verify at most two retries, a new reservation per attempt, exactly one settlement per reservation, and preservation of unknown failed usage as `None`.

## Material limits

Exact quotations prove that the cited text exists in the selected source. They do not mathematically prove that a paraphrase follows from that text. Semantic relevance and entailment remain AI judgments; the review prompt rejects unsupported clauses, unrelated facts, wrong entities, and guessed absences, but this is not an absolute hallucination guarantee. Removing uncited passages closes a request-input gap; an AI reviewer still sees the cited union and must judge each claim using only its own cited IDs. The mechanical validator enforces ownership of returned witnesses, not the model's internal reasoning. The hard park-name mismatch checker recognizes the three supported parks; broader entity mismatches also rely on that semantic review. This distinction is explicit in the validator's documentation and should remain explicit in reporting.

The `selected_park=None` service path deliberately retains the historical multi-park/evaluation contract. The new UI always requires and supplies a selection. This review did not certify the separate diagnostic path as enforcing the UI's selected-park contract.

## Reviewed hashes

| File | SHA-256 |
| --- | --- |
| `app.py` | `184cea2601bd6a4b02d7fdf942901750435a0c5f37cefddde5994f7a7083650b` |
| `src/parkguide/chat.py` | `8aeb06cf2bc5b36bfed6a28b87a1e90ab5248a16bcdb0b38a5cf962ab7f5d53a` |
| `src/parkguide/generation.py` | `9d58aed0c2dcbd46782e6e5ce4ced369fd9bd5b0052e4bff37c5273d9f16a661` |
| `src/parkguide/claim_review.py` | `652fcf86710b5b2ecd7491c9dc043d3869a9ad78e4c7ea22189950e0e064c0c2` |
| `config/project.json` | `02f52c44bc41038e7f55c45f9f61defe5d1a7e94316b484a4c30c6e1b36b2253` |
| `tests/test_park_scope.py` | `f17be818a37bf031deed90cbb438a35bc1f32dfe8958704e0dc293a59524470b` |
| `tests/test_generation.py` | `e9b3b8626f5f93782b51b6b96c8b884c59e1f3776c5acdb9e57c85fca6f78b58` |
| `tests/test_azure_contract.py` | `8a79587456f8790bb3ae4912a484364d967e087100848394fd1a45a3e582e0fe` |
| `tests/test_claim_review.py` | `a3ac2dda9a32e87b4a9dedbe0feb2f8dbcc05b3fb116dd878fafc2c4ad2fdadf` |
| `tests/test_retry.py` | `c8c0a6f70ae0d3bdf036537995647d8e3ebd8c7a24ee5dfcc467611132e14a1b` |
