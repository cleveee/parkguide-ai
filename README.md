# ParkGuide AI

A course RAG chatbot for Yosemite, Yellowstone, and Grand Canyon. Each conversation selects one park and answers from a frozen corpus of public National Park Service pages, with citations and source previews.

[Open ParkGuide](https://parkguide-ai-dh24.vercel.app/) · [Research paper](reports/research-paper/ParkGuide_AI_Research_Paper.docx) · [Evaluation report](reports/GOLD_MATRIX_EVALUATION.md) · [Results by question](reports/GOLD_MATRIX_RESULTS.md) · [Course presentation](powerpoint/ParkGuide_AI_Presentation.pptx)

## Evaluation

The October 10, 2026 study compares 40 saved chatbot responses with references derived from five independent model configurations. **Human verification is pending:** this is a development diagnostic, and semantic grades come from one AI assessor.

| Measurement | Saved result |
| --- | ---: |
| Correct answer / refusal / clarification action | 37/40 (92.5%) |
| Full rubric pass, AI assessed | 21/40 (52.5%) |
| Required facts delivered, AI assessed | 55/75 (73.3%) |
| Delivered claims supported by their citations, AI assessed | 40/40 (100%) |

Citation support measures the claims the chatbot delivered; the lower fact coverage shows that answers still omit required information. These results describe the recorded local run at `4d3faaf`, not a fresh test of the deployed app.

![Saved gold-matrix outcomes with counts and denominator units](reports/figures/gold-matrix-v1/outcomes.png)

- [Report and limitations](reports/GOLD_MATRIX_EVALUATION.md) — methods, retrieval metrics, breakdowns, and failure analysis.
- [All 40 question results](reports/GOLD_MATRIX_RESULTS.md) — actions, fact coverage, behaviors, and rubric outcomes.
- [Charts and exact figure data](reports/figures/gold-matrix-v1/README.md) — overall outcomes, evidence coverage, and action errors, with PNG/SVG downloads.
- [Mechanical metrics](artifacts/gold-matrix-v1/metrics.json), [semantic summary](artifacts/gold-matrix-v1/semantic-summary.json), and [per-case metrics](artifacts/gold-matrix-v1/per-item-metrics.jsonl).
- [Reference dataset](data/evaluation/gold-matrix-v1/gold-consensus.jsonl), [saved responses](artifacts/gold-matrix-v1/chatbot/responses.jsonl), and [provenance manifest](artifacts/gold-matrix-v1/result-manifest.json).

Reproduce and check the saved results without credentials or model calls:

```sh
.venv/bin/python scripts/evaluate.py
# Refresh derived results and reports after evaluation-code changes:
.venv/bin/python scripts/evaluate.py --write
```

See [the evaluation workflow](docs/EVALUATION_WORKFLOW.md) for setup, validation, dataset boundaries, and fresh-run requirements.

The [updated research paper](reports/research-paper/ParkGuide_AI_Research_Paper.docx) incorporates the charts, exact denominators, and failure analysis in Section 7. [Revision notes and the original manuscript](reports/research-paper/README.md) document the changes and the remaining human-review and held-out-evaluation gaps.

## Run locally

Use Python 3.12–3.13 and Node.js 24. The repo includes the frozen SQLite corpus and embeddings.

```sh
bash scripts/setup.sh
cp .env.example .env  # first setup only; fill in the approved Azure settings
bash scripts/run_web.sh
```

Open `http://127.0.0.1:8513`. Live chat uses the configured Azure resource. Offline evaluation replay uses saved responses and needs no Azure credentials. [Azure setup](docs/AZURE.md) · [Vercel profile](docs/VERCEL.md)

## Repository guide

| Location | Contents |
| --- | --- |
| `src/parkguide/`, `server.py` | Python retrieval, generation, safeguards, evaluation, and FastAPI backend |
| `web/` | React, TypeScript, Vite, and Tailwind frontend |
| `data/` | Frozen NPS corpus, SQLite database, embeddings, and reference datasets |
| `artifacts/` | Saved runs, raw labels, traces, and generated metrics |
| [reports/](reports/README.md) | Current evaluation report and historical course reports |
| [docs/](docs/README.md) | Setup, architecture, evaluation workflow, and historical development notes |
| `scripts/`, `tests/` | Reproduction tools and offline contract tests |

Run offline tests with `.venv/bin/python -m pytest -q`. Generated reports and saved research evidence are versioned; environments, secrets, build output, and test caches are ignored.
