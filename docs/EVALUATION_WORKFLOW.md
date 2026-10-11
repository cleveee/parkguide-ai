# Evaluation workflow

The current published study is `gold-matrix-v1`: 40 single-park questions, five independent labeling configurations, 75 consensus facts, and 40 saved chatbot responses collected on October 10, 2026. Human reference verification is pending. Its one-assessor semantic grades are provisional and its questions have prior development exposure.

[Evaluation report](../reports/GOLD_MATRIX_EVALUATION.md) · [Question results](../reports/GOLD_MATRIX_RESULTS.md) · [Reference dataset](../data/evaluation/gold-matrix-v1/gold-consensus.jsonl)

## Reproduce saved results

From the repo root, use the existing `.venv`. For a fresh clone, install Python 3.12–3.13 and run `PARKGUIDE_CORE_ONLY=1 bash scripts/setup.sh`; the frozen database is already included. Evaluation replay requires no `.env`, Azure credentials, network, or new model calls.

```sh
.venv/bin/python scripts/evaluate.py
```

The command validates frozen input identities, recomputes mechanical metrics, re-aggregates the existing semantic assessments, and renders both reports in a temporary directory. It compares that bundle with the saved derived files and exits nonzero on invalid inputs, missing outputs, or stale results. Only top-level generation timestamps are ignored; source timestamps, content hashes, metric values, and report text remain checked. A passing replay establishes reproducibility, not human correctness or current chatbot performance.

After changing scoring or report code, refresh the derived files and verify them:

```sh
.venv/bin/python scripts/evaluate.py --write
.venv/bin/python scripts/evaluate.py --check
.venv/bin/python -m pytest -q
```

Write mode finishes validation and generation in a temporary directory before copying the derived bundle into the repo. It updates only `agreement.json`, `metrics.json`, `qrels.json`, `per-item-metrics.jsonl`, `semantic-summary.json`, `dataset-audit.json`, and `result-manifest.json` under `artifacts/gold-matrix-v1/`, plus the two `GOLD_MATRIX_*.md` reports. Review and commit these derived changes together with scoring changes.

The tracked `result-manifest.json` also seals historical provenance. If it is missing or damaged, restore it from a trusted Git revision before replay; `--write` refuses to invent replacement input seals. Other missing or malformed derived outputs can be regenerated once those seals validate.

## Inputs and outputs

| File or directory | Role |
| --- | --- |
| `data/evaluation/gold-matrix-v1/` | Frozen question/source packet, AI consensus references, and reference manifests |
| `artifacts/gold-matrix-v1/reviewers/` | Original independent labels, source checks, and configuration provenance |
| `artifacts/gold-matrix-v1/chatbot/` | Immutable original chatbot responses and run identity |
| `artifacts/gold-matrix-v1/semantic-*` | Frozen assessor packet, saved AI judgments, provenance, and derived summary |
| [Mechanical metrics](../artifacts/gold-matrix-v1/metrics.json) | Action classification, retrieval, evidence coverage, and recorded latency |
| [Semantic summary](../artifacts/gold-matrix-v1/semantic-summary.json) | Aggregated required facts, behavior requirements, delivered claim support, and full rubric passes |
| [Question results](../reports/GOLD_MATRIX_RESULTS.md) | All 40 outcomes joined by case ID |
| [Report](../reports/GOLD_MATRIX_EVALUATION.md) | Findings, per-park/category breakdowns, failures, provenance, and limitations |

An action match only checks whether the chatbot answered, refused, or clarified as expected. A full rubric pass also requires the saved assessor's fact, behavior, and claim checks to pass. Citation identity checks that a cited chunk exists; citation support additionally judges whether its text supports the claim.

Chunk relevance requires a single chunk to contain one complete declared evidence group. Required-fact coverage can combine evidence across several chunks. Its denominator includes every answerable case with required facts, even if no single chunk qualifies as relevant. The report shows the mean per-case coverage; the JSON also retains pooled fact numerators and denominators.

## Fresh chatbot runs and human review

Replay preserves the source corpus, raw model labels, consensus, saved chatbot responses, and semantic assessments. It cannot improve the recorded chatbot answers or create new judgments.

The existing `scripts/gold_matrix.py bot` collector refuses to overwrite the completed run. A fresh experiment needs its own run directory, frozen dataset/configuration/build identities, budget check, and actual response collection, followed by a separate semantic assessment tied to those new responses. Do not delete the existing responses to bypass that guard or reuse old semantic judgments for new answers. The replay command does not launch paid collection.

The original source-authored course drafts and their authoring seal are separate from this AI consensus diagnostic. Human verification, a reviewed development/test split, and the final-test acceptance gates in [EVALUATION.md](EVALUATION.md) remain prerequisites for the formal course benchmark. No sealed final test is executed by replay.

The [18-question labeling sample](AI_LABELING_SAMPLE.md), [hallucination pilot](../reports/hallucination-experiment-20261010/REPORT.md), and earlier development/dialogue runs remain separate historical experiments. Their counts are not added to this study. The original independent review JSON files retain their October 10 scope; they do not certify later evaluator changes.
