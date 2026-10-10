# Azure Luna generation and evidence

All hosted inference now uses the existing Azure embedding resource:
`https://rd-foundry-dev-eastus2.cognitiveservices.azure.com`.
Robin's October 10, 2026 instruction replaces the original GPT-4 generator with Luna. The local SQLite database, frozen corpus and existing embeddings remain unchanged.

| Function | Deployment sent to Azure | Returned model |
| --- | --- | --- |
| Document/query embeddings | `text-embedding-3-small` | `text-embedding-3-small` |
| Answers and claim review | `gpt-6-luna` | `gpt-6-luna-2026-09-22` |

## Shared configuration

The ignored mode-0600 `.env` contains only four Azure variables: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, and `AZURE_OPENAI_GENERATION_DEPLOYMENT`. The endpoint/key are shared. The generation configuration takes its canonical endpoint from `embedding.endpoint`; a different resource, deployment environment, provider or returned snapshot is rejected. Separate generation endpoint/key settings are rejected. There is no direct OpenAI API branch, credential fallback or model substitution. The Python SDK is named `openai`, but its explicit base URL is this Azure resource's `/openai/v1/` route.

The project key was already authorized for the dev/staging resource. The old separate OpenAI key was removed from ParkGuide's private file. ReviewDoc files and services were not modified; no new resource or deployment was created.

## Independent live verification

`artifacts/setup/azure-luna-discovery.json` records read-only model-catalog availability, official Microsoft pricing and the unavailable Azure CLI account. Availability alone did not establish the deployment name. A minimal inference request using the snapshot string as deployment returned HTTP 404 and remains recorded. An explicit request to deployment `gpt-6-luna` then returned HTTP 200 and exact snapshot `gpt-6-luna-2026-09-22` at 14:24 UTC on October 10.

The successful probe accepted strict JSON, temperature 0, `reasoning_effort=none`, `store=false`, and `max_completion_tokens=128`. Usage: 44 input / 14 output tokens; elapsed 1,416.9 ms. The paired embedding probe used the same resource/key, returned one finite normalized float32 vector of dimension 1,536, used 8 tokens and took 431.0 ms. Both smoke attempts remain in `artifacts/setup/azure-luna-smoke-*.json`. Full answer/review calls retain the application's 1,000-token ceiling and are measured separately in the park-scope runs.

## Adapter contract

`generate(question, context, history, closed_book=False)` returns action, reconstructed answer, factual claims with evidence IDs, actual token usage, elapsed time, requested deployment, returned model/provider, and the exact message/schema hash. Actual earlier user/assistant messages resolve references; a supplied system role is rejected and assistant history never becomes evidence.

Answers and claim review use one `Generator.request(messages, schema)` helper, with temperature 0, reasoning disabled, 1,000 completion tokens, strict JSON and `store=False`. SDK retries and HTTP redirects are disabled. The caller owns up to two bounded retries for transient errors; Azure's numeric Retry-After is respected up to 60 seconds. Longer hints stop the request rather than retrying early. A missing 429 hint waits 60 seconds. Each attempt has its own priced reservation; unknown usage retains that reservation.

Grounded output is rebuilt from declared claims. Unknown/duplicate IDs, uncited claims, truncation, malformed output, missing usage and unapproved returned models fail validation. Selected-park malformed output becomes a controlled refusal; credential/configuration failures remain operational errors. Claim review requires complete decisions and exact saved-text witnesses for every retained citation. This is an AI entailment check, not a guarantee of accuracy. See [park scope](PARK_SCOPE.md) and [claim review](CLAIM_REVIEW.md).

Closed-book B0 remains a clearly labeled legacy evaluation mode on the same Azure generator. It is unavailable in the park-selector UI. No gold/test boundary was changed: all 40 authored drafts remain human review pending, and the formal split/test remains unconsumed.

## Cost estimates and history

Microsoft publishes Luna Standard short-context rates of $0.10/$0.50 per million input/output tokens for Global Standard, $0.11/$0.55 for US Data Zone, and $0.12/$0.60 for EU Data Zone. The budget uses the highest of these, $0.12/$0.60, with no cache discount. Requests use short contexts. Deployment SKU and account billing remain unverified; these are conservative Standard list-price estimates, not invoice totals. [Microsoft published Luna rates](https://azure.microsoft.com/en-us/blog/gpt-6-astra-sol-and-luna-for-production-agents-in-microsoft-foundry/).

Embeddings retain the conservative published East US 2 $0.022/M estimate. Historical seven-stage diagnostics used `gpt-4.1-mini-2025-04-14` through direct OpenAI at then-recorded $0.40/$1.60/M. Those artifacts and their per-event rate snapshots remain unchanged. New Luna operational runs are not a paired model-quality benchmark or a regrading of old results. The ledger includes all historic usage, failed-call reservations and new Azure usage under the existing $5 cap.

Offline tests verify Azure-only routing, resource/model drift, no credential/provider fallback, no redirects/retries, shared answer/review settings, safe errors and usage settlement. Live smoke establishes connectivity and accepted parameters; selected-park diagnostics and browser checks establish observed app behavior. None substitutes for human source or answer review.
