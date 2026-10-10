# Vercel hosted profile

ParkGuide can run as one native FastAPI project on Vercel at the repository root. The entry point is `server.py`, a thin wrapper around `parkguide.web.app`. The legacy Streamlit `app.py` is never the entry point, and it is not uploaded. This profile serves the same React app and the same shared `parkguide.chat.answer` path. It uses the same frozen SQLite database and the one approved Azure resource. It creates no database service, Azure resource or Vercel Services/Large Functions setup.

This document covers preparation only. Importing the project, adding credentials and deploying are done by Robin. A live deployment has not been created or verified.

## Import settings

| Setting | Value |
|---|---|
| Root directory | `.` (repository root) |
| Framework preset | FastAPI |
| Build / install / output | Leave automatic; `vercel.json` and `pyproject.toml` supply them |
| Python | 3.12 (`.python-version`; `[tool.vercel] entrypoint = "server:app"`) |
| Node.js | 24.x (`package.json`) |

Build command (from `vercel.json`): `npm --prefix web ci && npm --prefix web run build && python scripts/prepare_vercel.py`.

`scripts/prepare_vercel.py` makes no Azure call and never ingests, migrates or re-embeds anything. It:

1. verifies `data/parkguide.sqlite` against its frozen size and hash (56,664,064 bytes, SHA-256 `2e017b08…5c`), its counts (155 documents, 5,405 chunks, 5,405 vectors, two builds) and its active structure-aware build;
2. checks that `gold_drafts_ready()` passes with the two gold-seal files;
3. writes the public `cl100k_base` tokenizer file to `vendor/tiktoken/`. tiktoken downloads it from `openaipublic.blob.core.windows.net` if needed and verifies its SHA-256. This is the only application-data fetch in this preparation step; dependency installation also downloads packages;
4. copies `web/dist` to `public/`, which Vercel serves from its CDN. It refuses to copy `.sqlite`, `.jsonl`, `.py`, `.lock`, `.env` or tokenizer files.

## Environment variables (server only)

Set these in Vercel Project Settings → Environment Variables. They are server-only. Do not add any `VITE_*` or other browser-exposed variable. Credentials can be added after the first build; redeploy afterwards.

| Name | Value |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | the approved endpoint already in `config/project.json` |
| `AZURE_OPENAI_API_KEY` | the key for that resource (secret) |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-small` |
| `AZURE_OPENAI_GENERATION_DEPLOYMENT` | `gpt-6-luna` (the config pins snapshot `gpt-6-luna-2026-09-22`) |
| `PARKGUIDE_PUBLIC_ORIGIN` | optional, exact `https://host` of a custom domain |

The application refuses any other endpoint or deployment, as it does locally.

## What differs from the local profile

The hosted profile is selected by `VERCEL=1`, which Vercel sets. The offline tests use `PARKGUIDE_HOSTED=1` to select it.

| | Local (unchanged) | Hosted (Vercel) |
|---|---|---|
| Retrieval | hybrid cosine + BM25 + RRF, then cross-encoder rerank for selected-park chat | hybrid cosine + BM25 + RRF, **no reranker** |
| Context | 5 passages, 1,600-token budget | same |
| Generation, claim review, quote/integrity guards | Luna via the approved resource | identical |
| SQLite | read-write for CLI index/migration commands | opened `mode=ro&immutable=1` on every read path, including `store._connection`; a missing file is an error and is never created |
| Query-embedding cache | `data/embedding-cache/` | `/tmp/parkguide/embedding-cache/`, separate and ephemeral on each instance |
| Budget ledger | `artifacts/api-ledger.json`, one shared ledger, $5 cap | `/tmp/parkguide/api-ledger.json`, $5 cap **per instance** |
| Request serialization | one answer at a time per process | one answer at a time per instance |
| Tokenizer | tiktoken default cache | bundled `vendor/tiktoken/`, with `TIKTOKEN_CACHE_DIR` set before any encoding is created |

The hosted bundle does not include PyTorch or sentence-transformers. This keeps the function small and avoids a model download or cold start. Retrieval is therefore not the configuration that was evaluated. **The recent selected-park web checks used the local reranker. Historical development stages used several local variants; none measure hosted retrieval accuracy.** `/api/meta` (`runtime`, `models.reranker.enabled`, `retrieval.selected_park_rerank`), each chat turn's `runtime` block, the How it works dialog and the inspector all report the effective profile. All historical evidence is unchanged.

**The budget cap is not global.** Each Vercel instance keeps its own ledger in `/tmp`. The ledger resets whenever an instance is recycled, and concurrently running instances do not share it. The per-instance lock only serializes requests within one instance. For the credential-backed demo, deployment protection and provider rate/quota controls can limit access and request volume. Azure budget alerts alone do not enforce a hard spending cap. A global application spending cap would require a durable shared ledger, which this simple deployment does not add. No additional resources or controls were provisioned.

## Request protection

- **Host allowlist:** the Host header must exactly match `VERCEL_URL`, `VERCEL_PROJECT_PRODUCTION_URL` or the host of `PARKGUIDE_PUBLIC_ORIGIN`. These are server-side environment variables; values with wildcards, ports, paths, userinfo or a non-https scheme are ignored. `X-Forwarded-Host` and other client-supplied forwarding headers are never trusted. Other `*.vercel.app` hosts, including branch aliases, get 421.
- **Write checks:** POST requires an exact `https://` `Origin` matching the request Host (production, preview and custom hosts cannot write across origins), `application/json` and a declared body of at most 64 KiB.
- **Errors and headers:** errors use fixed safe codes, and middleware adds the security headers. `vercel.json` applies the same CSP, `nosniff`, `Referrer-Policy`, `X-Frame-Options` and COOP headers, plus HSTS, to files served from the CDN.
- **Server-only files:** the database, config, the two gold-seal files (`data/evaluation/gold-draft-manifest.json`, `gold-drafts.jsonl`) and the tokenizer cache are in the function bundle only. They are never in `public/`, and the function serves only files in `public/`.

## Bundle contents

`.vercelignore` keeps the following out of the upload: `.env*`, virtual environments, `node_modules`, `app.py`, `dashboard/`, `tests/`, the lock files, `data/raw/`, `data/embedding-cache/`, `data/diagnostics/`, `data/documents.jsonl`, `artifacts/`, `reports/`, `docs/`, and all evaluation files except the two gold-seal files. The `functions["server.py"]` include/exclude globs in `vercel.json` also remove `web/`, `scripts/`, `public/assets/` and caches from the function. Python dependencies come from `requirements.txt`, whose pins match `requirements-full.lock`, and from the matching bounded `[project].dependencies`. Ingestion (`ingest`), Streamlit (`app`) and reranking (`rerank`) are optional extras that the hosted install does not include. Local setup (`scripts/setup.sh` with the full lock) is unchanged.

## Not verified here

These remain unverified until the project is imported and built on Vercel:

- an actual Vercel build;
- the measured function size;
- how `.vercelignore` negation and `includeFiles` behave on Vercel;
- the cold-start time;
- a live hosted chat.

Check them after import, and check that `/api/health` reports `"profile": "vercel"`.
