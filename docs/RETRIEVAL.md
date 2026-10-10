# Local storage, chunking, and retrieval

The implemented modules use the existing SQLite schema, NumPy exact dense search, and BM25. No database server or vector service is required. The contracts below are locally verified with deterministic fixture vectors/scores; those tests do not establish real corpus quality or model performance. Cloud callbacks and live corpus measurements belong to the root integration/evaluation work.

## Source and chunk provenance

`chunking.chunk_documents(docs, strategy='fixed', target=200, overlap=40)` accepts ingestion dictionaries or documents returned by `store.load_documents`. Each source includes normalized text and ordered paragraph/table blocks with character offsets into that text. Source offsets are checked before chunking. SQLite stores normalized text, blocks, table status, and raw hash together in `normalized_blocks_json`.

Both strategies count their complete model input using `cl100k_base`, including heading prefixes and repeated table headers. Unicode-aware token offsets select original character slices; text is neither silently truncated nor decoded into replacement characters. An oversized heading/header raises an explicit budget error instead of disappearing.

- Fixed chunks use token-bounded windows with overlap and the starting block's heading path.
- Structure chunks pack adjacent paragraphs under the same heading, split oversized paragraphs, and keep tables separate. Markdown table rows stay intact when they fit; each table chunk repeats its original header. Oversized rows split with explicit fragment spans and repeated headers.

Every chunk includes its full heading metadata, source character spans, token count, and an ID hashed from source document/content revision, tokenizer/chunker configuration, spans, and actual text. `chunk_statistics` returns counts and token minimum/maximum/mean/p50/p95. Gold evidence remains attached to source spans, so each strategy can derive its own chunk relevance labels without rewriting the questions.

## Store functions and atomic builds

Functions in `store.py` take a local database path:

```python
initialize(db)
save_documents(db, docs)
docs = load_documents(db)
manifest = build_index(db, docs, 'fixed', embedder,
                       model_config=embedding_config,
                       target=200, overlap=40,
                       activate=True, delete_previous=False)
chunks = load_chunks(db, build_id=manifest['build_id'])
```

The callback `embedder(list_of_texts)` returns an `(n, dimension)` matrix. Store validates count/dimension, finite values, nonzero norms, and optional configured dimensions. It normalizes and persists contiguous little-endian float32 vectors. The manifest records model configuration, corpus and chunker identity, ordered IDs/hashes, vector checksum, statistics, source metadata snapshot, and UTC creation time.

Embedding completes before SQL import. Documents, build manifest, chunks, vectors, and active-build switch then commit in one transaction. Failed embeddings never replace the usable build; SQL import failure rolls back every inserted/updated row. Existing complete builds with the same identity reuse their saved vectors without calling the embedder. An incomplete existing build is rejected rather than disguised as a cache hit.

Inactive builds remain queryable for B1/B2/B3 and controlled ablations. Explicit `activate_build(db, build_id, delete_previous=True)` performs migration and cascading deletion of the former active build. Root integration performs this destructive migration demonstration on a database copy to retain experiment baselines. Re-chunking requires only saved normalized sources and the callback/cache; it does not crawl. Frozen vectors/cache are needed if the demonstration also prohibits embedding API requests.

`delete_document` cascades through all builds' chunk/vector rows. Retrieval loads fresh rows on each call, so deletions and activation changes need no long-lived index cache invalidation. `delete_build` removes its derived rows. Deletion changes the live contents of an originally recorded build; preserve original manifests/results when reporting experiments. `integrity_report` reads foreign-key errors, orphan vectors, missing vectors, active builds, and row counts. Empty/incomplete builds cannot be activated.

## Retrieval contract

```python
result = retrieve(db, query, query_vector, mode='hybrid',
                  build_id=None, filters={'parks': ['yose', 'yell']},
                  rerank=False, candidate_count=20,
                  per_retriever_fetch=40, final_count=5, rrf_k=60)
```

`build_id=None` selects the active build. `query_vector` is optional only for BM25. Dense mode checks dimension/finite values/nonzero norm and computes the dot product after query normalization, matching stored L2-normalized vectors. BM25 applies identical lowercase alphanumeric tokenization, function-word removal and narrow pet/carry word normalization to corpus and query; numbers and negation remain. Follow-up keyword queries retain earlier subjects with duplicate tokens removed. When the latest question names a concrete detail, its BM25 candidates must contain at least one of those current terms, preventing old-topic-only matches from gaining a second rank-fusion vote. Bare date/pronoun/generic-action follow-ups have no such gate. Dense search always embeds the full resolved query and its candidates remain unrestricted by the keyword gate. The trace exposes the separate `keyword_query` and gate terms. Each mode uses stable chunk-ID tie-breaking. Hybrid combines up to 40 ranks from each retriever using `sum(1 / (60 + rank))`, then keeps 20 unique candidates.

Filters apply before scoring. Supported keys are `park`, `parks`, `page_type`, `doc_id`, `source_url`, `effective_date`, `effective_date_from`, and `effective_date_to`. Park codes `yose`/`yell`/`grca` and full park names are accepted; comparison lists form a union. Date filters exclude unknown effective dates instead of treating them as current. Empty/short pools return explicit `shortfall`; filters are never relaxed silently. Unknown filter keys fail.

The result includes:

- `candidates`: original candidate order, scores and per-retriever ranks.
- `reranked`: full post-rerank order, preserving pre/post positions and score types.
- `final`: at most five passages for generation.
- Build/filter identity, candidate/eligible counts, shortfall, and local load/retrieval/rerank/total timings.

Each passage includes chunk/document IDs, text, title, URL, heading path, source type/hash/date, raw `source_span_json`, and parsed `source_span`/`source_spans`. Normalized-source spans and complete contexts support evidence coverage and citation validation separately from URL presence.

Reranking accepts a supplied callback taking `(query, text)` pairs, or lazily loads the approved CrossEncoder on CPU. It reads the matching model revision from root configuration; the resolved MiniLM fallback revision is `233902d25c440f23af6f7d6e94d2946bac0bee0a`. Before real-model scoring, every query/passage pair is tokenized with the model's actual tokenizer without truncation. Pairs exceeding the model limit raise an explicit error; the trace records token lengths. It validates score count/finiteness and preserves the original trace. Reranking is an assignment requirement even though its dependency remains an optional install extra. Model download/loading time is included in a cold first-call trace; use a documented warm-up policy before measured comparisons. The candidate pool limits reranking's evidence recall. Model scores are not calibrated answer confidence. [Sentence Transformers teaching example](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).

## Verified contracts

```sh
.venv/bin/python -m pytest tests/test_store_retrieval.py -q
```

The focused suite covers deterministic Unicode-safe bounded chunks; complete source-span coverage; repeated table headers/rows; heading boundaries; SQLite source roundtrips; candidate counts, filters, and shortfalls; BM25 and RRF scores; complete rerank traces; cached-build no-call reuse; failed embeddings and SQL rollback; rejected incomplete activation; offline migration; cascading deletion; and invalid query vectors. Fixture tests use no provider API. Real source retrieval metrics and actual reranker results must be reported separately from these contracts.

## Actual local model check

On October 9, 2026, the pinned model loaded and scored real CPU inference locally. Installed versions were Sentence Transformers 6.1.0, Transformers 5.19.0, Torch 2.14.1, and NumPy 2.5.3; `pip check` found no broken requirements. A three-pair synthetic check produced raw logits 6.71 for fee evidence and −10.98 for an unrelated passage, with 31.24 ms prediction time after loading. These invented passages establish an operational model path, not ParkGuide answer quality.

The actual retrieval/model integration retained 20 original candidates, a full 20-result reranked order, and five final passages. Its synthetic relevant document ranked first. Actual tokenizer pair lengths were 24–27 tokens. The cold call took 7.40 seconds including model loading. With the model already loaded, three observed local totals were 170.23, 32.21, and 30.88 ms; this small synthetic check is not a corpus latency distribution and excludes cloud embeddings/generation.

Secret-free evidence lives under ignored `artifacts/retrieval/`: `reranker-smoke.json`, `reranker-pipeline-smoke.json`, and `reranker-pipeline-warm-smoke.json`. The requested model revision was the pinned SHA above; cached configuration/weight/tokenizer files were verified to belong to that snapshot and hashed. Transformers did not expose a returned `_commit_hash`, so the artifact distinguishes the requested/cached revision from that unavailable model field. No Azure or generation request was made by these checks. The latest focused suite passed **19 tests**, including rejection before scoring when an actual-tokenizer pair would exceed 512 tokens.
