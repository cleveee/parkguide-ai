# ParkGuide implementation status

**The local PoC now uses one existing Azure resource for embeddings, answers and claim review.** Formal course evaluation remains HUMAN_REVIEW_PENDING. The repo is `/Users/robin/Build/Personal/parkguide-ai`, on `main`, with a public archive at [cleveee/parkguide-ai](https://github.com/cleveee/parkguide-ai). The initial working Azure/Streamlit version is commit `bdbba39`; the [repository data snapshot](REPOSITORY_DATA.md) documents publication of non-secret corpus, database, caches and run evidence. Nothing has been deployed or submitted.

Open [ParkGuide](http://127.0.0.1:8511) and the [updated run dashboard](../dashboard/index.html). The UI requires one park, clearly indicates it, filters every search to that park and clears history when the selection changes. Every delivered factual claim requires cited saved passages and mandatory AI support review. Missing, live, private and wrong-park information is withheld. AI review can still make semantic mistakes or over-refuse; it is not a guarantee of correctness.

## Current Azure-only configuration

| Item | Verified state |
| --- | --- |
| Shared resource | `https://rd-foundry-dev-eastus2.cognitiveservices.azure.com`; same endpoint/key for all hosted inference |
| Embeddings | `text-embedding-3-small`; frozen 1,536-dimensional normalized float32 vectors reused |
| Answers and review | Deployment `gpt-6-luna`; returned snapshot pinned to `gpt-6-luna-2026-09-22` |
| Request settings | Strict JSON, temperature 0, reasoning none, 1,000 completion tokens, store false; redirects and SDK retries disabled |
| Configuration | Four Azure variables; no direct OpenAI key/configuration or provider fallback |
| Rate limits | Up to two caller retries respecting numeric Azure Retry-After up to 60 seconds; longer hints stop instead of retrying early |
| Offline verification | 290 tests passed in 1.18 seconds; pip check clean; 202 targeted Azure/scope/review/retry tests |
| Source isolation | Reviewer receives only the union of claim-cited passages; exact source witnesses are resolved from short catalog IDs |
| Live browser | Three actual turns: cited answer, cited follow-up and missing-fact refusal; selected banner, all three parks, disabled empty selection, source cards/excerpts and history reset verified |

Independent paired Azure smoke evidence is in `artifacts/setup/azure-luna-smoke-20261010T142410Z-05470fb5.json`. The snapshot spelling was not the deployed alias and returned 404 in the preceding preserved probe. The successful alias returned the exact target model; the paired embedding returned the expected vector using the same credentials/resource. [Generation details](GENERATION.md) record actual usage, settings, prices and remaining SKU/billing uncertainty.

## Current selected-park diagnostics

The latest immutable run is `artifacts/park-scope/20261010T143500Z-50f15a2d`. It completed all **21/21 requests** across six actual three-turn conversations and three singleton missing-fact checks, preserving preceding history snapshots of 0/2/4 messages. **20/21 expected-action and boundary checks matched**: 11 answers and 10 refusals. There were no application, review-schema or guard errors. Wall time was 116.12 seconds, including actual provider waits/cache behavior.

One ordinary-soft-backpack follow-up was withheld because the generated blanket rule was not established by its cited passage. Its usefulness/over-withholding status remains an AI-review uncertainty. The final independent AI audit found the 12 delivered claims provisionally supported by their cited saved text; this is not human accuracy. The table answer now cites its DW legend, container qualifiers are retained, and the drone answer cites the actual rule. See `artifacts/park-scope/azure-support-audit-final.json`. Earlier failures, the prior AI audit and all six scoped runs remain in the dashboard; they are neither overwritten nor relabeled. New operational matches are not a benchmark regrading or a controlled model-quality comparison.

Live UI evidence: `artifacts/ui/park-scope-verification.json`, `azure-final-browser-proof.json`, and `park-selector-preview.png`. The independent offline review is `artifacts/ui/park-scope-review.md`. [Park scope](PARK_SCOPE.md) explains enforced boundaries and semantic limits.

## Preserved corpus and historical diagnostics

The unchanged corpus contains **155 NPS documents: 150 HTML, five PDFs and 45 table-bearing documents**. Fixed chunks: **1,698**; structure-aware active chunks: **3,707**. SQLite retains **5,405 validated vectors** across two builds with zero foreign-key errors. Corpus/query embedding configuration and stored vectors were not rebuilt for the generator migration. Offline migration proof remains on a database copy with zero network calls/stale IDs/orphans.

The original **seven stages / 305 attempted rows / 66 provisional AI labels** used the older direct OpenAI GPT-4 generator. Their raw outputs, prices and artifact hashes remain unchanged. Historical final baseline run: `artifacts/runs/20261010T042905Z-54d33f15`; six-dialogue run: `artifacts/dialogues/7bbd1b0ccdb649edbaf2b64ccc9797e3`. These describe 48 baseline responses and 18 conversation turns. Historical selected B3 matched 12 expected actions and used no reranking. Its eight evidence-bearing diagnostics had coverage@5/@20=8/8, MRR 0.854 and nDCG@10 0.891. Provisional AI review found 16 clear / two uncertain conversation turns and 36/38 supported selected-B3/dialogue claims; those did not establish the proposed 90%/95% gates or human accuracy.

The current selected-park UI enables the existing local reranker after a scoped safety-passage retrieval miss; the legacy unselected CLI/diagnostic default remains off. This is a new configuration, separate from the historical ablation. Original source-card replay retains 307 page cards / 336 passages across 196 historical answers. Dates describe the saved snapshot, not live conditions.

The full API ledger remains below the approved $5 cap. The dashboard includes historic costs, new Azure usage and conservative reservations for failures with unknown tokens. Amounts are dated list-price estimates; deployment SKU/invoice rates remain unverified. Each ledger event keeps its own rate snapshot, so older GPT-4 usage is not repriced as Luna. The initial separate embedding probes add approximately $0.000000748 to the ledger estimate.

## Remaining human work

1. Review all 40 gold drafts against saved source spans and mark the actual verifier/date. Use `data/evaluation/GOLD_REVIEW.md`; original sealed content is archived at `data/evaluation/gold-authored-original.jsonl` with its original hash. Do not replace human review with model judgments.
2. Confirm at least 15 real failure labels from `reports/failure-review.jsonl`. The 22 proposals are actual observed initial outputs, each tied to its immutable run/item. No human label has been filled.
3. Run the reviewed seeded 24/16 split; develop only on 24 dev items. Review the proposed gates, prepare a genuinely approved acceptance record using `scripts/prepare_final_review.py`, then run B0–B3 once on the same 16 held-out items. Acceptance tracks live source/chunk/vector content, code/configuration, and dataset hashes.
4. Complete the classroom demonstration and remaining team/course deliverables when separately authorized. Robin authorized a public GitHub code/data archive on October 10; that publication is separate from a course submission or deployment.

Known limits: rotated PDF chart headers, possible PDF column interleaving, pattern-based contact redaction, source age, incomplete alternative-evidence judgments, and an AI reviewer that can falsely approve an unsupported claim. Historical dialogue traces through stage6 contain later turns due to mutable-history aliasing; their real requests used preceding history, and the stage7 traces fix the snapshot error. The user-requested example.com crawler contact remains a course contact-email exception.

Corpus SHA-256: `2d1285fed3c6b9960496999daa4dff4656df40c20c10d89c821c913db8d9589d`. Original gold SHA-256: `15117b5270cf0ffee2917b5fa2ab87496e3be4628860cda7bf77e6b933a8de47`. Secrets are mode 0600 in ignored `.env`; raw data, databases, embeddings, models and artifacts stay local. Codex and three scoped subagents implemented and reviewed this work; no agent certified human verification.
