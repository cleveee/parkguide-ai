# ParkGuide working instructions

Robin approved implementation on October 9, 2026 with "go for it". The current phase is implementation. Read README.md, docs/PLAN.md, docs/EVALUATION.md, docs/AZURE.md, docs/RESEARCH.md, and config/project.json before work.

docs/IMPLEMENTATION_PROMPT.md is active. Continue implementation and actual development evaluation within its gates; do not fabricate human review or final-test results. Robin confirmed instructor topic approval and requested a placeholder crawler contact; those inputs are resolved for this local scope. Human gold verification remains pending.

Keep the application and SQLite database local. Do not add a remote, commit, push, deploy, provision resources, modify ReviewDoc, or send messages to people unless Robin later authorizes that action. Robin's October 10 simplification authorizes the one existing Azure development embedding resource for embeddings and Luna generation/claim review. No direct OpenAI API or alternate resource is permitted. Credentials belong only in ignored .env or process environment; never expose keys, authorization headers, or secret-bearing errors in logs, Git, reports, or chat.

Use subagents for scoped implementation, evaluation, and independent review when implementation is approved. Give each agent file ownership and integrate changes through the root agent. Preserve human gold verification and sealed-test boundaries. Agents cannot claim human review, fabricate results, relabel failures as passes, or tune on final test results.

Continue actual development and evaluation through multiple measured stages and six live conversations of at least three user turns each. Read docs/EVALUATION.md for gates and limits. Reaching a budget or iteration limit is incomplete work, not success. If a real human dependency blocks a stage, continue independent work and report exactly what remains.

Keep code small and explicit: Python, sqlite3, NumPy, rank-bm25, Streamlit, direct provider SDK, JSONL artifacts. Add a framework or service only when an observed limitation justifies it.
