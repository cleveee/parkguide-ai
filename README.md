[Open ParkGuide on Vercel](https://parkguide-ai-dh24.vercel.app/)

## Eval

[Read the evaluation report](reports/GOLD_MATRIX_EVALUATION.md)

Five model configurations independently labeled 40 single-park questions. The report compares their consensus with 40 fresh chatbot responses using precision, recall, F1, source support and completeness. AI-derived references and semantic grades await human review.

## Tech stack

React, TypeScript, Vite, and Tailwind CSS for the frontend; Python and FastAPI for the backend. SQLite stores the frozen NPS corpus. Retrieval combines NumPy cosine search and BM25; Azure OpenAI provides embeddings and Luna answer generation and source review. Hosted on Vercel.
