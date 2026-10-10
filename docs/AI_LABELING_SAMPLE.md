# Independent AI reference-labeling sample

Robin requested three independent subagents and Claude Code CLI on October 10, 2026. This study creates reference-answer proposals for comparison. It does not certify human gold labels, run the sealed final benchmark, or grade the chatbot.

## Frozen inputs

The sample has 18 newly worded questions, three in each of six purposively chosen strata: factual, multi-hop, comparative, temporal, unavailable information, and ambiguous/adversarial. It covers Yosemite, Yellowstone, and Grand Canyon. This is a coverage sample, not a random estimate of performance. The author had already seen development questions and failures; overlapping themes are disclosed in `sampling-plan.json`.

Inputs are saved under `data/evaluation/ai-labeling/sample-v1/`. The original `source-packet.json` includes ten complete normalized source documents and their block offsets, metadata for all 155 corpus documents, and lexical search records for unavailable requests. `annotation-input.json` is an exact content projection with redundant block representations removed, shared by all reviewers. Its SHA-256 is `96521432f3fd7c73835d60fb0b107e2dbd098208182f1d4140d379b7b4156839`. Root checked all provided normalized source text and block offsets against the frozen read-only SQLite database. `manifest.json` preserves database, original-gold and input hashes.

`instructions.txt` and `labels.schema.json` define one common rubric: expected action and answerability, a proposed answer, required facts, forbidden contradictions, exact evidence quotes, rationale and self-assessed confidence. Quotes are limited to 25 whitespace-separated words each. Cross-park comparisons are allowed for this corpus-QA study; production's single-park UI policy is a separate concern.

## Independent reviewers

Product-scope limitation: AL07–AL09 require answers across two parks and are unsuitable for the current one-park-per-chat knowledge suite. Their immutable labels are retained as corpus-QA evidence only. The later [functionality audit and product-aligned revision](EVALUATION_FUNCTIONALITY.md) supplies explicit park setup and single-park alternatives without modifying this study's frozen inputs or reviewer outputs.

Codex A, B and C are three fresh-context subagents inheriting the parent model. They are independent runs of the same model, not three different models. Each is instructed to read only its own input copy and write only its own labels/provenance. They receive no existing gold answers, chatbot outputs, other labels or reports. This isolation is enforced by task instructions and separate input directories, not filesystem access controls.

Claude Code CLI runs from a separate input-only temporary directory, using its configured default model without an override or fallback. Safe mode disables customizations, hooks and memory; tools, Chrome, session persistence and external MCP configurations are disabled. The exact schema is supplied using `--json-schema`, with a $3 CLI API budget ceiling. Actual returned model usage, CLI cost and execution metadata are saved separately. This is a specifically user-requested external labeling run; it does not change the application's Azure provider, use its credentials, or make application/embedding requests.

All four outputs are retained separately under `artifacts/ai-labeling/sample-v1/{codex-a,codex-b,codex-c,claude-code}/`. Root does not rewrite their expected answers, force consensus, or mark a majority vote as correct.

## Validation and comparison

`python3 scripts/compare_ai_labels.py` validates the frozen inputs, unchanged database/original gold, JSON schemas, complete case coverage, source identities and exact evidence quotations. It resolves quotes to character offsets and flags multiple occurrences or facts without mechanically valid quotes. These are source-integrity checks, not semantic proof.

The script creates `comparison.json`, `REVIEW.md`, each reviewer's `source-validation.json`, and `data/evaluation/ai-labeling/sample-v1/reference-candidates.jsonl`. The latter preserves all four proposed references and leaves `adjudicated_reference`, `human_verifier` and `verified_at` empty. Every record remains `human_review_pending` and `benchmark_eligible: false`.

`REVIEW.md` presents proposed answers side by side and reports action/answerability agreement. It intentionally does not score semantic answer equivalence or accuracy: shared agreement can repeat the same mistake. Compare required facts, exclusions and source context before choosing a reference. A human must approve, revise or reject candidates and record a real name/date before any human-gold claim.

The ten full documents are a curated evidence pack; corpus-wide lexical scans and URL metadata do not mean a reviewer semantically inspected all 155 documents. All conclusions concern saved public NPS information, not live availability, private bookings or the entire internet. Confidence labels are subjective, not calibrated probabilities.

The pre-existing 40 gold drafts and their pending human-verification state remain unchanged. No sealed test was created or consumed, and no chatbot behavior was tuned on this sample.

## Execution scripts

- `scripts/prepare_ai_label_sample.py` creates the initial source packet from the existing database and refuses to overwrite it.
- `scripts/run_claude_label_sample.py` makes one bounded CLI run from the recorded isolated workspace and refuses to overwrite a successful response. The exact input/rubric/schema are archived; temporary directories can be reconstructed from them. It does not silently retry a semantic failure.
- `scripts/compare_ai_labels.py` regenerates comparison and review artifacts from the saved original outputs without making model calls.

## Recorded outcome

All four reviewers completed 18 labels each, for 72 annotations. All 18 actions and answerability categories are unanimous, but semantic equivalence and accuracy were not scored. Root verified 284 exact source quotes with no mechanical evidence errors. Claude Code reported `claude-opus-5-5`, two internal CLI turns in one invocation, and $1.105736 in CLI-reported usage. The run stayed below its $3 ceiling. No application or embedding calls were made.

`artifacts/ai-labeling/sample-v1/human-review-queue.json` highlights questions about required pet exceptions, the January year, explicit PDF prose versus a blank table cell, and legitimate unquoted absence/ambiguity observations. These remain review questions, not accepted corrections. `label-manifest.json` freezes the four original label/provenance files.

The private-booking identifier is a synthetic test placeholder; no real private reservation data was used. The files are saved locally for review and comparison.
