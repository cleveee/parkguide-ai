# Research paper

[ParkGuide AI research paper](ParkGuide_AI_Research_Paper.docx) is the original Word document supplied on October 11, 2026, preserved byte for byte. Its content and formatting have not been revised. This folder is documentation and is already excluded from the Vercel bundle by the repository's `reports/` rule.

Source filename: `ParkGuide_AI_Research_Paper.docx`. Size: 219,863 bytes. SHA-256: `946a6b88243e4253e7ded4eb3a40de1c42d5a9a6cad29c426bea469ec9afc624`.

## Evaluation coverage review

**The end-to-end RAG development evaluation is present.** Section 7, Table 2, on page 3 of the reviewed rendering reports the same 40-question study as the [evaluation report](../GOLD_MATRIX_EVALUATION.md). It measures actual retrieved-context answers and refusals, including generation and claim checks, rather than only reference-label agreement. The [recorded run metadata](../../artifacts/gold-matrix-v1/chatbot/metadata.json) identifies local `chat.answer` execution on October 10 at commit `4d3faaf`, hybrid retrieval, no reranker, and Luna generation. Each question starts with one selected park and empty history.

| Measurement in Table 2 | Verified saved result |
| --- | ---: |
| Correct action | 37/40 (92.5%) |
| Full rubric pass, one AI assessor | 21/40 (52.5%) |
| Required facts delivered, AI assessed | 55/75 (73.3%) |
| Delivered claims supported, AI assessed | 40/40 (100%) |
| MRR / nDCG at 10 | 0.794 / 0.769 |
| Mean per-case evidence coverage at 5 / 20 | 84.2% / 96.7% |
| Recorded latency p50 / p95 | 4.14 s / 34.92 s |

The figures match [mechanical metrics](../../artifacts/gold-matrix-v1/metrics.json) and the [semantic summary](../../artifacts/gold-matrix-v1/semantic-summary.json). The four Wilson intervals in the paper also reproduce from their stated numerators and denominators under the stated independence assumption. Offline replay passed during this review; no new model calls or human judgments were made.

## What remains missing

The **formal human-verified, held-out gold benchmark** has not been completed. The [consensus manifest](../../data/evaluation/gold-matrix-v1/consensus-manifest.json) records human review pending and `benchmark_eligible=false`. The planned reviewed 24/16 split and frozen B0–B3 final-test comparison remain pending. Table 1's earlier 12-question diagnostic with a different generator does not satisfy that benchmark.

The same 40-question matrix has not measured the deployed Vercel/API/browser path or multi-turn conversations. Its settings match the hosted retrieval profile, but its execution and latency are local. Separate historical browser and dialogue checks do not convert this matrix into a hosted or multi-turn benchmark. See the [workflow](../../docs/EVALUATION_WORKFLOW.md) and [course evaluation gates](../../docs/EVALUATION.md).

## Corrections to make in a future paper revision

1. **Separate the two datasets in Section 7's design paragraph.** Original course drafts were sealed before the first outputs. The [product-aligned consensus dataset](../../data/evaluation/gold-matrix-v1/manifest.json) used revised candidates after earlier development exposure. It does not inherit the original drafts' pre-output authoring claim or a completed development/test split. The paper's Table 2 caption already acknowledges prior exposure; the design paragraph should make the same distinction.
2. **Name the actual run in Table 2.** Replace the broad “current system” label with the October 10 local 40-question diagnostic and its commit. Describe it as end-to-end backend RAG evaluation and retain the pending-human-review qualification.
3. **Keep metric denominators consistent in the error analysis.** Delivered-fact coverage is pooled across 75 facts, while 84.2% and 96.7% are means over 30 answerable cases. The comparable pooled evidence figures are 63/75 (84.0%) in generation contexts and 72/75 (96.0%) at 20 candidates. Subtracting the original percentages does not quantify losses at each stage; per-fact source coverage and the assessor's semantic judgments must be aligned first. The M036 refusal also involves a numeric guard, so not every missing answer is solely a generation failure.
4. **Qualify the Wilson intervals.** Their arithmetic is correct, but several facts and claims share a question and questions can share sources. The independent-observation intervals are descriptive and do not account for those dependencies, reference uncertainty, or the sample's prior development exposure.
5. **Link the complete evaluation artifacts.** The paper summarizes the main results. The repository also reports behavior satisfaction (30/42), action precision/recall/F1, and chunk retrieval precision/recall/F1. Link [all question results](../GOLD_MATRIX_RESULTS.md) and the [full report](../GOLD_MATRIX_EVALUATION.md) so readers can inspect these dimensions and the recorded failures.

These are review findings, not edits to the supplied manuscript. The paper's existing human-review and development-diagnostic caveats should remain.
