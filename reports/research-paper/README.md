# Research paper

The [updated research paper](ParkGuide_AI_Research_Paper.docx) incorporates three charts, exact metric denominators, and the recorded failure analysis from the saved `gold-matrix-v1` experiment. Sections 7 and 8 were revised and Robin Cleve's engineer contribution was added on October 11, 2026. The paper remains an editable Word document; the [original supplied manuscript](source/ParkGuide_AI_Research_Paper.docx) is preserved byte for byte.

Original source: `ParkGuide_AI_Research_Paper.docx`, 219,863 bytes, SHA-256 `946a6b88243e4253e7ded4eb3a40de1c42d5a9a6cad29c426bea469ec9afc624`. The [revision manifest](revision-manifest.json) records the updated paper's hash and its source, metric, figure, and builder identities. This directory is excluded from Vercel by the repository's `reports/` rule.

## Results incorporated

The end-to-end backend RAG development evaluation is present. The [saved run metadata](../../artifacts/gold-matrix-v1/chatbot/metadata.json) identifies local `chat.answer` execution on October 10 at commit `4d3faaf`, hybrid retrieval, no reranker, and Luna generation including claim checks. Each question starts with one selected park and empty history. This revision reuses those responses and saved assessments; it makes no new model calls.

| Measurement | Saved result |
| --- | ---: |
| Correct action | 37/40 questions (92.5%) |
| Full rubric pass, AI assessed | 21/40 questions (52.5%) |
| Required facts delivered, AI assessed | 55/75 facts (73.3%) |
| Behavior requirements satisfied, AI assessed | 30/42 requirements (71.4%) |
| Delivered claims supported, AI assessed | 40/40 claims across 27 answers (100%) |
| MRR / nDCG at 10 | 0.794 / 0.769 over 30 answerable cases |
| Pooled declared evidence coverage at 20 / in contexts | 72/75 (96.0%) / 63/75 (84.0%) |
| Recorded local latency p50 / p95 | 4.14 s / 34.92 s |

The [complete evaluation report](../GOLD_MATRIX_EVALUATION.md), [all 40 question results](../GOLD_MATRIX_RESULTS.md), and [chart data and downloadable figures](../figures/gold-matrix-v1/README.md) accompany the manuscript.

## What changed

- Separated the original course gold drafts from the later product-aligned AI consensus dataset, whose questions had prior development exposure.
- Named the actual local run date, code commit, retrieval profile, and assessor. The earlier GPT-4.1 mini baseline table and its exploratory results remain separate.
- Added overall outcome, evidence/answer, and action-confusion figures, plus behavior compliance, chunk retrieval rates, and a table covering all 19 unsuccessful cases.
- Distinguished pooled coverage across 75 facts from the mean of 30 per-question fractions. The evidence and semantic measures are not a nested funnel; differences do not quantify causal losses between stages.
- Replaced the independent-observation Wilson intervals with explicit counts and a dependency caveat. Facts and claims share questions, questions share sources, and reference/assessor uncertainty is not captured by those intervals.
- Added links and offline reproduction instructions, and normalized title/heading styling.
- Added Robin Cleve's approved engineer contribution covering the RAG pipeline, Azure and SQLite integration, React/FastAPI app, park selection, source previews, retrieval inspectors, reliability improvements, Vercel deployment, testing, and technical documentation. Other contribution entries and unrelated historical statements are retained.

## What remains missing

The **formal human-verified, held-out gold benchmark remains pending**. The [consensus manifest](../../data/evaluation/gold-matrix-v1/consensus-manifest.json) records pending human review and `benchmark_eligible=false`. Neither this matrix nor the earlier 12-question baseline comparison completes the planned reviewed 24/16 split and frozen B0–B3 final-test comparison.

This 40-question study also does not measure the deployed Vercel/API/browser path or multi-turn conversations. Settings match the hosted retrieval profile, but execution and latency are local. All semantic grades come from one AI assessor and have not been calibrated against human judgments.

## Reproduce

Use the [evaluation workflow](../../docs/EVALUATION_WORKFLOW.md#charts-and-research-paper). `scripts/build_research_paper.py --check` validates the saved paper and its inputs without Word dependencies. `--write` requires the optional `reports` dependencies and rebuilds the revised sections and Robin's contribution from the archived original, checked metrics, checked figures, and approved contribution text in the builder. Render and inspect every page after rebuilding; a hash check does not verify Word layout.
