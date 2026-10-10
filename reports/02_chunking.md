# Chunking and offline migration

These are implementation reports. Gold verification, semantic grading, and the final held-out benchmark remain subject to real human review. Diagnostic scores are not assignment-valid gold accuracy.

Both strategies count complete inputs, retain source spans, and enforce a 200-token limit. Fixed overlap is 40 tokens; structure-aware chunks retain headings/table headers.

```json
{
  "statistics": {
    "fixed": {
      "chunk_count": 1698,
      "document_count": 155,
      "tokens": 327898,
      "minimum": 48,
      "maximum": 200,
      "mean": 193.10836277974087,
      "p50": 200.0,
      "p95": 200.0
    },
    "structure": {
      "chunk_count": 3707,
      "document_count": 155,
      "tokens": 324448,
      "minimum": 5,
      "maximum": 200,
      "mean": 87.52306447261937,
      "p50": 62.0,
      "p95": 200.0
    }
  },
  "migration": {
    "previous_builds": [
      "5a6a37ba5cdd3e57bc888a77df31752630c3c6d79e1dbbc9a56f82db6ada8627"
    ],
    "deleted_previous": true,
    "active_build": "e372e28772f9266c175804450969b9879998a97b1d8dd8792f3e3f8cc194dd1a",
    "integrity": {
      "documents": 155,
      "index_builds": 1,
      "chunks": 3707,
      "embeddings": 3707,
      "foreign_key_errors": 0,
      "orphan_vectors": 0,
      "chunks_without_vectors": 0,
      "active_builds": 1
    },
    "previous_build_rows_remaining": 0,
    "network_requests": 0,
    "normalized_sources_reused": true,
    "previous_chunk_count": 1698
  }
}
```

Migration proof is performed on a database copy so baseline experiments remain reproducible. See docs/RETRIEVAL.md.
