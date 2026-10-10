# One Azure resource for the local PoC

Status: the existing Azure dev/staging embedding service passed an independent live request, and its selected credential is configured in this project's private `.env`. The database and chat application remain local. Subsequent implementation populated both indices and exercised the chatbot; see [STATUS.md](STATUS.md). Cloud scope is existing hosted APIs, with local execution/storage and no remote VM.

## Verified independent request

| Item | Observed value |
| --- | --- |
| Test time | October 9, 2026, 9:19:33 p.m. America/Chicago (CDT) |
| UTC time | `2026-10-10T02:19:33.300214+00:00` |
| Environment | ReviewDoc dev/staging shared embedding resource; production was not called |
| Endpoint | `https://rd-foundry-dev-eastus2.cognitiveservices.azure.com/openai/v1/embeddings` |
| Requested deployment | `text-embedding-3-small` |
| Returned model | `text-embedding-3-small` |
| Authentication | Azure resource API key through the `api-key` header |
| API route | `v1`; no `api-version` query parameter |
| Input | `ParkGuide connectivity check: this is public, synthetic text.` |
| Input count | 1 |
| HTTP result | 200 |
| Elapsed time | 1,411.7 ms for this request |
| Returned vectors | 1 |
| Vector dimension | 1,536 |
| Vector values | All finite |
| Observed L2 norm | `1.00019418` |
| Provider token usage | 12 prompt tokens; 12 total tokens |

The test called the service directly with a standalone Python process. It did not start ReviewDoc, access its database, run its logging, or submit application documents, evaluation answers, or chat history. The vector itself was not persisted. The secret-free report was transcribed from the completed probe output and is retained locally at `artifacts/setup/azure-independent-smoke.json`, which Git ignores.

This independent check was one request. It verifies this endpoint, credential, route, deployment, and returned vector shape at that time. It does not measure batching throughput, concurrency, sustained rate limits, query latency distribution, or capacity in other Azure regions.

## Verified ParkGuide adapter

The project's own adapter also passed a real two-input synthetic batch on `2026-10-10T02:24:32.176535+00:00`. It returned two finite 1,536-dimensional vectors in 3,346.8 ms, used 22 tokens, restored input order, and normalized the float32 outputs to L2 norm 1.0. The saved NumPy file hash is `3f62cba31e7a5e5bef516e24a290cdbcdf6b25498daceb5009b0f87e007dae81`. Evidence and vectors are retained under ignored `artifacts/setup/azure-project-smoke*` paths.

Eight deterministic boundary tests passed separately, covering output ordering/normalization, incomplete/duplicate/nonfinite/zero vectors, failure-body suppression, and no-request rejection of inherited endpoint/deployment mismatches. The adapter checks the environment against `config/project.json` before HTTP. These are contract checks, not retrieval or chatbot evaluations. The adapter is in `src/parkguide/azure.py`. To explicitly repeat the paid synthetic check, run `.venv/bin/python scripts/smoke_azure.py`; ordinary setup/doctor makes no model calls.

## Private configuration and provenance

The credential came from:

- Source file: `/Users/robin/Build/ReviewDoc/web-app-main/.env.local`
- Variable: `AZURE_EMBEDDING_ENDPOINT_POOL`
- Selected entry: `eastus2`
- Selected host: `rd-foundry-dev-eastus2.cognitiveservices.azure.com`
- Authentication type: resource API key, not a Microsoft Entra bearer token

ReviewDoc's resource-map and infrastructure documentation identify the `rd-foundry-dev-{region}` shared pool as dev/staging, with separate `rd-foundry-prod-{region}` resources. The canonical ReviewDoc checkout was inspected read-only. Its preexisting Git status remained unchanged after the probe and credential selection.

Only the selected key and the following three variables were placed in ParkGuide's `.env`:

```dotenv
AZURE_OPENAI_ENDPOINT=https://rd-foundry-dev-eastus2.cognitiveservices.azure.com
AZURE_OPENAI_API_KEY=<private selected dev resource key>
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
```

The file was confirmed ignored before it was created, written exclusively without overwriting an existing file, and set to mode `0600`. No ReviewDoc database settings, general model pools, chat-generation keys, or other variables were copied. The setup parsed the named variable and selected entry directly; it did not shell-source or evaluate the source file. Never print the key, log authorization headers, place it in a manifest, or commit `.env`.

The source `.env.local` also contains `AZURE_AI_API_VERSION=2025-04-01-preview`. That belongs to the legacy versioned route and was neither needed for the successful v1 request nor copied into ParkGuide.

## Request and vector contract

For the configured root endpoint, construct `POST /openai/v1/embeddings`. Set `Content-Type: application/json` and pass the private key through `api-key`. Send the deployment name as `model`, a string or array of strings as `input`, and `encoding_format: "float"`. Keep TLS verification enabled. Microsoft documents this v1 route, the optional version query, and API-key authentication in the [Azure embeddings API reference](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/embeddings).

Use the same endpoint/provider, deployment, dimension, and preprocessing configuration for corpus and query embeddings. Validate vector count and response indices against input order, the expected 1,536 dimensions, finite values, and a nonzero norm. Normalize each vector to unit length, convert it to float32, and validate the stored representation before adding it to the local SQLite build. Record normalization as part of the embedding configuration.

Cache corpus and query embeddings by a key derived from the normalized text hash and embedding configuration: provider, endpoint, deployment, dimensions, API route, preprocessing version, normalization, and dtype. Rechunking changes chunk IDs and text hashes; unchanged text may reuse a verified cached vector under the same configuration. Import a completed corpus build atomically, preserving the last usable build when a batch fails.

Handle 429 and temporary 5xx failures with bounded retries, the provider's retry guidance, and resumable caching. Never convert authentication errors or partial output into successful embeddings. Record actual token usage and request timing so evaluation cost and latency are measured from real calls. Dated published prices are recorded in config/pricing.json and combined with provider token usage. Azure resource SKU/invoice attribution is unverified; estimates are not a billing statement.

## Reproducibility and cloud scope

The response reports `text-embedding-3-small` but does not expose the underlying deployment model revision. Deployment names can retain the same spelling when their model changes. Do not claim immutable model-version reproducibility from that name alone.

Persist the generated float32 vectors and their ordered chunk IDs with checksums. The run manifest should include requested deployment, returned model, endpoint, v1 route, requested/output dimension, dtype, normalization, preprocessing version, corpus/config hashes, request dates, observed token usage, and vector/output hashes. Reuse that frozen embedding artifact when comparing retrieval configurations. If the deployment is deliberately changed or new checks show incompatible vectors, start a new embedding configuration and rebuild the index.

An additional remote worker, GitHub remote, cloud VM, cloud database, or deployment is unnecessary for this PoC's embedding generation. The approved existing Azure service performs the cloud computation, and local code receives vectors for local storage and retrieval. The current generator is the independently verified `gpt-6-luna` deployment returning `gpt-6-luna-2026-09-22` on this same resource, documented in GENERATION.md. The OpenAI-named Python SDK is configured with this explicit Azure base URL; no request goes to the direct OpenAI API.

## Completed bulk implementation

The final corpus has 150 HTML pages and five PDFs. Azure generated 1,698 fixed-chunk vectors and 3,707 structure-aware vectors, all stored as normalized finite 1,536-dimensional float32 values. The active local build is structure-aware; both builds remain for controlled comparisons. A larger 64-input batch timed out; verified cache reuse and 16-input batches completed the builds. Failed calls retain conservative cost reservations. Thread-local HTTP sessions avoid carrying broken connections between concurrent requests. Original provider vectors and manifests are retained locally; Azure deployment revision remains unexposed.

The initial setup used this Azure key for embeddings. Historical generation briefly used a separate OpenAI credential. Robin's October 10 simplification removed that key from ParkGuide's ignored mode-0600 `.env`. The same Azure key now serves both deployments. No ReviewDoc app or database was modified.

## Paired Luna and embedding verification

On October 10 at 14:24 UTC, an independent direct request to this resource's `/openai/v1/chat/completions` returned HTTP 200 for deployment `gpt-6-luna`, with the exact returned snapshot `gpt-6-luna-2026-09-22`. Strict JSON, temperature 0, `reasoning_effort=none`, `store=false` and a 128-token smoke ceiling were accepted; usage was 44 input and 14 output tokens, elapsed 1,416.9 ms. The paired project embedding call used the same endpoint/key and returned a finite normalized float32 1,536-dimensional vector, 8 tokens, elapsed 431.0 ms.

The snapshot string itself was not the deployment name and returned HTTP 404 in the preceding recorded probe. Both attempts remain in `artifacts/setup/azure-luna-smoke-*.json`. Model-catalog discovery and official pricing are recorded in `azure-luna-discovery.json`. SKU/invoice attribution remains unverified. Full app requests use the established 1,000-token ceiling and are measured separately in the selected-park diagnostics. Rate-limit retries respect Azure's numeric Retry-After up to 60 seconds and remain capped at two retries.
