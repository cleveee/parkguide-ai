# Figures from the saved ParkGuide RAG experiment

These figures summarize the **October 10, 2026 local run**: 40 single-park questions, AI-consensus references, and semantic grades from one AI assessor. Human review remains pending. The questions have prior development exposure; these are diagnostic results, not a held-out benchmark or a measurement of the current deployment. Figure generation makes **zero new provider calls**.

[Exact chart data and input hashes](chart-data.json) · [Figure hashes and rendering provenance](figure-manifest.json) · [Evaluation report](../../GOLD_MATRIX_EVALUATION.md) · [All question results](../../GOLD_MATRIX_RESULTS.md)

## Overall outcomes

![Outcome percentages with exact counts and scoring units](outcomes.png)

**Figure 1.** The chatbot matched the expected action on 37/40 responses, while 21/40 passed the full provisional rubric. The assessor marked 55/75 required facts delivered, 30/42 behavior requirements satisfied, and 40/40 delivered claims supported. The last denominator contains claims from 27 answer cases; it does not mean all 40 responses were complete or correct. Each bar labels its own scoring unit.

[PNG](outcomes.png) · [SVG](outcomes.svg)

## Evidence and answer measurements

![Pooled declared evidence coverage and delivered fact counts](evidence-and-answer.png)

**Figure 2.** Against the same 75 reference facts, declared source-span evidence covers 72/75 facts in the top 20 ranked chunks and 63/75 in the actual generation contexts. The semantic assessor marked 55/75 facts delivered. These are separate measurements, not a causal funnel: four delivered facts do not meet complete declared-context evidence coverage. Declared evidence groups are not exhaustive supporting alternatives. The pooled percentages, 96.0% and 84.0%, differ from the report's mean per-case coverage, 96.7% and 84.2%.

[PNG](evidence-and-answer.png) · [SVG](evidence-and-answer.svg)

## Action confusion matrix

![Expected versus observed answer, refuse, and clarify actions](action-confusion.png)

**Figure 3.** Expected actions are rows and observed actions are columns. All three action mismatches are over-refusals: 3/30 answerable questions received refusals. All eight expected refusals and both expected clarifications matched their action labels. An action match does not establish that the response satisfied its fact or behavior requirements.

[PNG](action-confusion.png) · [SVG](action-confusion.svg)

## Reproduce or verify

From the repository root, verify the saved data and PNG/SVG hashes with the standard-library-only check:

```sh
python3 scripts/build_gold_matrix_figures.py --check
```

Rendering additionally requires the optional report dependencies. It uses the saved responses and judgments and never calls a model:

```sh
.venv/bin/python -m pip install '.[reports]'
.venv/bin/python scripts/build_gold_matrix_figures.py --write
.venv/bin/python scripts/build_gold_matrix_figures.py --check
```

The [generator](../../../scripts/build_gold_matrix_figures.py) exposes `build_data()` without a plotting dependency. Use `--output-dir PATH` for a separate output bundle. `--write` stages rendering before publishing the three PNG/SVG pairs, deterministic data, and manifest; `--check` validates their identities without importing Matplotlib. Aggregate input hashes omit only the top-level `created_at` timestamp, so unchanged metric replay does not invalidate the figures.

The figures show no confidence intervals: facts and claims cluster within responses, and some questions share topic families. Preserve the AI-assessment, sample-selection, and local-run limits when reusing these images. The [saved responses](../../../artifacts/gold-matrix-v1/chatbot/responses.jsonl), [semantic assessments](../../../artifacts/gold-matrix-v1/semantic-assessment.json), and [reference dataset](../../../data/evaluation/gold-matrix-v1/gold-consensus.jsonl) remain unchanged.
