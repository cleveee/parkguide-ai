# Retrieval and reranking development evidence

These are implementation reports. Gold verification, semantic grading, and the final held-out benchmark remain subject to real human review. Diagnostic scores are not assignment-valid gold accuracy.

| Variant | Items | Errors | Evidence@5 | Evidence@20 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 12 | 0 | N/A | N/A | N/A | N/A |
| B1 | 12 | 0 | 1.000 | 1.000 | 0.875 | 0.908 |
| B2 | 12 | 0 | 1.000 | 1.000 | 0.550 | 0.662 |
| C1 | 12 | 0 | 1.000 | 1.000 | 0.854 | 0.891 |
| C2 | 12 | 0 | 1.000 | 1.000 | 0.854 | 0.891 |
| B3 | 12 | 0 | 1.000 | 1.000 | 0.781 | 0.837 |

Standard chunk Recall@5/@20 and other denominators are retained in the saved summary JSON. Evidence coverage uses immutable source spans; chunk qrels are rebuilt per strategy. Compare fixed dense → structure dense → hybrid → reranker one factor at a time. These are non-gold diagnostics. Reranker scores are relevance scores, not confidence probabilities. The pre-rerank pool is limited to 20; post-rerank context is at most five.

Controlled run: /Users/robin/Build/Personal/parkguide-ai/artifacts/runs/20261010T035053Z-24ef6136

In that historical run B3 labels the reranking ablation. Current final B3 uses structure-aware hybrid with reranking disabled by default; the local reranker remains integrated and selectable. See docs/DIAGNOSTIC_ANALYSIS.md and docs/CANDIDATE_ANALYSIS.md for paired intervals, ceiling, and measured added latency. No positive reranker lift was established.
