[Open ParkGuide on Vercel](https://parkguide-ai-dh24.vercel.app/)

## Evaluation

[Read the evaluation report](reports/hallucination-experiment-20261010/REPORT.md)

The evaluation compares chatbot answers with saved official NPS sources across single-park conversations, follow-ups, tables, exceptions, and source limitations. The current pilot audits 39 recorded responses for unsupported claims, missing conditions, incomplete answers, and unnecessary refusals. Source evidence, annotations, and reproducible results are saved with the report. The semantic judgments are provisional; independent evaluator and human review remain pending.

## Tech stack

React, TypeScript, Vite, and Tailwind CSS for the frontend; Python and FastAPI for the backend. SQLite stores the frozen NPS corpus. Retrieval combines NumPy cosine search and BM25; Azure OpenAI provides embeddings and Luna answer generation and source review. Hosted on Vercel.
