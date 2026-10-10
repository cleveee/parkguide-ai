# Research behind the local PoC plan

Primary documentation and educational source code checked on October 9, 2026. These are design recommendations; retrieval quality, latency, cost, and extraction accuracy have not been benchmarked on the ParkGuide corpus.

## Recommended stack

Use one Python application with a local SQLite file, exact NumPy vector search, `rank-bm25`, Streamlit, and the direct `openai` SDK. Reuse the existing ReviewDoc TEST Azure embedding deployment. Verified endpoint settings, API family/version, deployment name, underlying model, vector dimensions, and usage budget belong in [AZURE.md](AZURE.md). The UI and database run locally; calling an existing Azure endpoint does not deploy this application.

| Part | Choice and rationale |
| --- | --- |
| Storage | Python's built-in [`sqlite3`](https://docs.python.org/3/library/sqlite3.html): documents, chunks, metadata, index versions, and float32 embedding BLOBs in one database file. |
| Dense retrieval | NumPy matrix multiplication after normalizing document and query vectors. [Official OpenAI documentation](https://developers.openai.com/api/docs/guides/embeddings) describes cosine similarity and the equivalent dot product for unit vectors. |
| Keyword retrieval | [`rank-bm25`](https://github.com/dorianbrown/rank_bm25): a small, inspectable BM25 implementation. Apply identical tokenization to corpus and query. |
| UI | [`streamlit`](https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps): Python chat widgets and session history; tables/expanders can expose retrieval traces. |
| Web extraction | [`requests`](https://requests.readthedocs.io/en/latest/) and [`beautifulsoup4`](https://www.crummy.com/software/BeautifulSoup/bs4/doc/): save original bytes, then parse headings, paragraphs, links, and tables. |
| PDF extraction | [`pdfplumber`](https://github.com/jsvine/pdfplumber): text plus explicit table extraction. Inspect extracted tables; scanned PDFs need a separately justified OCR path. |
| Cloud calls | The initial adapter uses Requests with the verified Azure v1 `api-key` contract; the `openai` SDK handles generation. [`tiktoken`](https://developers.openai.com/api/docs/guides/embeddings) counts tokens using the underlying model's encoding, not an arbitrary deployment alias. |
| Reranking | Optional package extra `sentence-transformers`; implement a [`CrossEncoder`](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) reranker when reaching that phase. Reranking itself remains a course requirement. |

Core third-party dependencies: `numpy`, `rank-bm25`, `streamlit`, `openai`, `requests`, `beautifulsoup4`, `pdfplumber`, and `tiktoken`; add `sentence-transformers` for local reranking and `pytest` for meaningful verification. Use standard-library JSONL, hashing, robots parsing, command-line parsing, and statistics where sufficient. Resolve and pin versions after a setup smoke test.

## Keep retrieval visible

Load eligible vectors and IDs from SQLite, apply page-type/park filters, then compute exact similarity. An illustrative 5,000 chunks at 1,536 float32 dimensions occupy about 30.7 MB; actual corpus size and query latency still require measurement. [Sentence Transformers](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html) documents manual semantic search for relatively small collections.

Fetch up to 40 BM25 and 40 dense candidates. Fuse their union using [reciprocal rank fusion](https://cormack.uwaterloo.ca/cormack/cormacksigir09-rrf.pdf), keep at least 20 eligible unique candidates, rerank, and pass at most five to generation. Preserve each stage's IDs, ranks, scores, and timing. RRF combines ranks rather than incompatible BM25/cosine scores.

Save cleaned source blocks independently of chunks. Deterministic IDs should include source/content revision and chunker configuration. Rechunk from saved blocks, atomically activate the new index, remove old derived rows, and verify deletion with retrieval readbacks. Invalidate cached vectors/BM25 indexes after activation or deletion. These behaviors provide the assignment's migration evidence without another crawl.

Citation validation must check allowed evidence IDs and factual support separately. A clickable URL alone proves neither support nor correctness. Tune refusal behavior on development questions. Cross-encoder raw scores are logits; even sigmoid-scaled scores are not calibrated answer confidence. [Reranker documentation](https://sbert.net/docs/cross_encoder/pretrained_models.html)

## Educational references to adapt

- [Microsoft Azure embedding tutorial](https://learn.microsoft.com/en-us/azure/foundry/openai/tutorials/embeddings?view=foundry-classic): cleaning, token counting, SDK calls, and local semantic search. Adapt its SDK configuration to the TEST endpoint; its demonstration deployment is not our configuration. Microsoft's [embedding guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/embeddings) confirms that Azure requests use deployment names. Batch within verified model/request/rate limits, cache by content and model revision, and log usage.
- [Official Sentence Transformers Colab](https://colab.research.google.com/github/huggingface/sentence-transformers/blob/main/examples/sentence_transformer/applications/retrieve_rerank/retrieve_rerank_simple_wikipedia.ipynb): a concrete BM25/dense/cross-encoder teaching example. Inspected, not executed here. Replace its large Wikipedia download and unconditional `.cuda()` call. Its local embedding model is educational context; Azure remains this project's embedding default.
- [DataTalksClub evaluation module](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/04-evaluation/README.md): retrieval metrics, ground truth, and answer evaluation. Add this assignment's human verification of every reference answer and freeze the development/test split before examining chatbot outputs.

## Tools to defer

Start evaluation with JSONL cases, ordinary Python metric scripts, saved answers/traces, human grading, and paired comparisons. [Ragas](https://docs.ragas.io/en/stable/getstarted/rag_eval/), [DeepEval](https://deepeval.com/docs/getting-started), and [Promptfoo](https://www.promptfoo.dev/docs/intro/) are optional later aids; they add configuration/dependencies and do not replace verified gold answers or controlled experiments.

[Chroma](https://docs.trychroma.com/reference/python/client) provides an embedded persistent client, metadata filters, and deletion, but persists a directory. [FAISS](https://github.com/facebookresearch/faiss/wiki/Getting-started) adds a vector index while source metadata and stable ID mapping still need storage. Add either only when measured retrieval latency or corpus growth justifies it. Direct Python functions also avoid introducing LangChain/LlamaIndex orchestration before this small pipeline needs it.
