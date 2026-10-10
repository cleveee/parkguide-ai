# Vercel preparation: Claude Code implementation summary (2026-10-10)

Scope: a minimal native FastAPI Vercel profile in the existing repository. I ran no Git commands, made no deployment or account operations and no paid or Azure calls. I did not read `.env` or the evaluation content. Frozen data, vectors, `config/project.json`, pricing, `generation.py`, the evaluation logic and the Azure restrictions are unchanged.

## Changes

- **`src/parkguide/runtime.py`**: adds the profile helpers.
  - `hosted()` is true for `VERCEL=1`, or for `PARKGUIDE_HOSTED=1` as a test override.
  - `state_root()` is `/tmp/parkguide` when hosted; `PARKGUIDE_STATE_DIR` overrides it in tests.
  - Path helpers: `embedding_cache_dir()`, `ledger_path()` and `sqlite_uri()` (`mode=ro`, plus `immutable=1` when hosted).
  - `rerank_override()` returns False when hosted and None locally.
  - `runtime_profile()` holds the public profile, reranker, evaluation-note, budget-scope and serialization text.
  - `configure_environment()` sets `TIKTOKEN_CACHE_DIR=vendor/tiktoken` and HF offline at import when hosted. Local paths are unchanged.
- **`budget.py`**: the default `Budget()` ledger follows `runtime.ledger_path()`. `Budget(root)` with a custom root keeps `root/artifacts/api-ledger.json`. Pricing is still read from the bundled config. The cap is the configured $5; when hosted it applies per instance.
- **`embedding_cache.py`**: adds `cache_folder()` on top of `embedding_cache_dir()`. `web._observed_embedder` uses the same helper.
- **`store.py`**: `_connection(db, readonly=None)` defaults to read-only when hosted. That covers `retrieval.py`, `load_documents`, `get_manifest` and the other read paths. A missing database raises `FileNotFoundError` and is never created. Local writes are unchanged. `runtime` is imported before `chunking`.
- **`web.py`**:
  - Hosted host allowlist comes only from `VERCEL_URL`, `VERCEL_PROJECT_PRODUCTION_URL` and the optional exact `PARKGUIDE_PUBLIC_ORIGIN` (`https://host`, strict hostname regex, no wildcard, port, path or userinfo).
  - Hosted POSTs require an `https://` Origin. `X-Forwarded-Host` is not trusted. The 64 KiB, JSON and Sec-Fetch checks are kept.
  - Read-only connections use `sqlite_uri`. `DIST` is `public/` when hosted, so the shell fallback still works.
  - `/api/meta` gains `runtime`, `models.reranker.enabled`, an effective `retrieval.selected_park_rerank` and per-profile persistence text.
  - Each turn and each error's details carry a `runtime` block. Hosted chat passes `rerank=False`; local calls are unchanged. `/api/health` reports `profile`.
- **`server.py`** (new, at the repo root): adds `src` to the path, imports `runtime` first, and refuses to start when hosted without the bundled tokenizer. It exports `app`.
- **`pyproject.toml`**:
  - Runtime dependencies are reduced to requests, numpy, rank-bm25, openai, httpx, tiktoken, python-dotenv, fastapi and uvicorn, with bounded versions.
  - BeautifulSoup and pdfplumber move to the `ingest` extra, and Streamlit to the `app` extra. `rerank` and `dev` are unchanged.
  - `[tool.vercel] entrypoint = "server:app"`.
  - `requirements.txt` has exact pins from `requirements-full.lock`. `.python-version` is 3.12.
- **`vercel.json`**:
  - Build command: `npm --prefix web ci && npm --prefix web run build && python scripts/prepare_vercel.py`.
  - `functions["server.py"]` sets `maxDuration` 120 and include/exclude globs. Included: the database, the two gold-seal files, `config`, `src`, `vendor/tiktoken` and `public/index.html`. Excluded: `web`, `artifacts`, `reports`, `docs`, `tests`, `scripts`, raw corpus, caches, `app.py` and the locks.
  - CDN security headers and an immutable cache for `/assets/*`.
- **`.vercelignore`**: excludes `.env*`, environments, `node_modules`, `app.py`, `dashboard`, `tests`, the locks, raw/cache/diagnostics data, `artifacts`, `reports`, `docs`, and evaluation files except the two gold-seal files (by negation).
- **`.gitignore`**: adds `/public/`, `/vendor/tiktoken/` and `.vercel/`.
- **`scripts/prepare_vercel.py`**:
  - Verifies the database's frozen size, SHA-256, counts (155/5405/5405/2) and active structure build, and that `gold_drafts_ready()` passes.
  - Caches the public `cl100k_base` file through tiktoken, which verifies its hash.
  - Copies only `web/dist` to `public/`, refusing server-only suffixes.
- **Frontend** (`web/src/lib/api.ts`, `how-it-works.tsx`, `inspector.tsx`): adds `RuntimeProfile`/`TurnRuntime` types. When hosted, How it works shows hosted step text, a "hosted retrieval differs from evaluated setup" note and a per-instance budget note. When hosted, the inspector shows a runtime-profile row, the reranker-not-installed note and "Server function" location labels. Local text is unchanged.
- **Docs**: new `docs/VERCEL.md`; short sections added to `README.md` and `AGENTS.md`.
- **`tests/test_vercel.py`** (11 tests): hosts and origins (including spoofing, malformed origins and the body bound), local profile unchanged, writes in temp, read-only database that is missing or never created, web database-missing error, hosted chat forcing `rerank=False` with profile details, hosted `/api/meta` on the real frozen DB, packaging configuration, tokenizer cache name and SHA-256, and SPA publishing.

## Checks run

- `.venv/bin/python -m pytest -q`: **408 passed** (whole suite, offline).
- `.venv/bin/python scripts/prepare_vercel.py` (locally, not on Vercel):
  - Database verified: 155 documents, 5,405 chunks, 5,405 embeddings, 2 builds.
  - Tokenizer cached at `vendor/tiktoken/9b5ad71b2ce5302211f9c61530b329a4922fc6a4` (1,681,126 bytes; SHA-256 checked in the tests).
  - 4 files published to `public/`. It ran before the TSX edits, so the `public/` and `web/dist` copies are stale; both are gitignored.
- Offline hosted smoke run (`PARKGUIDE_HOSTED=1`, sockets blocked; bs4, pdfplumber, Streamlit, torch, sentence_transformers and transformers blocked):
  - `server` imports and the tokenizer loads from the vendored cache.
  - `/api/meta`: profile vercel, chat ready, 155 documents, 3,707 active chunks.
  - SPA shell returns 200, and the document listing works.
  - `retrieve(..., rerank=False)` returned 20 candidates and 5 final passages on the read-only DB.
  - No heavy module was imported.

## Not done / limitations

- **Frontend build not run.** `npm run build` and `tsc` needed permission approval in this session. The root agent should run `npm --prefix web ci && npm --prefix web run build` to typecheck the TSX edits.
- Not verified on Vercel itself:
  - an actual build;
  - the measured bundle size;
  - `.vercelignore` negation and `includeFiles` semantics;
  - whether `public/` is also included in the function;
  - the Linux wheel resolution of `requirements.txt`;
  - cold start;
  - a live hosted chat.
- The hosted reranker-off retrieval profile has not been evaluated. The saved evaluations measure only the local reranker-on profile.
- The hosted budget cap ($5) is per instance and ephemeral. It is not a global limit; Azure-side cost controls are recommended, and none were provisioned.
- Branch-alias URLs (`VERCEL_BRANCH_URL`) are deliberately not in the allowlist; preview access uses the deployment URL.
- When both files exist, Vercel's choice between `requirements.txt` and `pyproject.toml` was not confirmed. Both list the same minimal runtime set.
