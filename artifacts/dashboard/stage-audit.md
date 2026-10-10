# Stage audit

| Stage | Single-turn attempts | Dialogue attempts / completed / errors / unattempted | Completed-response p50 / p95 ms (single; dialogue) | Successful generation + review USD |
| --- | ---: | --- | --- | ---: |
| 1: Controlled representation and retrieval | 72 | 17 / 16 / 1 / 1 | 2091.3 / 3643.5; 2568.1 / 3599.8 | 0.08832920 |
| 2: History and prompt correction | 12 | 18 / 18 / 0 / 0 | 1844.1 / 3542.5; 1934.1 / 2925.5 | 0.03458520 |
| 3: Concise generation; reranking off | 12 | 18 / 18 / 0 / 0 | 1724.2 / 3290.0; 1557.3 / 2325.9 | 0.02875480 |
| 4: Paired selected versus reranked | 24 | 18 / 18 / 0 / 0 | 1682.9 / 2791.6; 1471.5 / 2153.9 | 0.03791080 |
| 5: Source-claim review and numerical guards | 12 | 18 / 18 / 0 / 0 | 2744.1 / 5023.2; 2307.2 / 3596.3 | 0.04831240 |
| 6: Captured table-page filtering | 0 | 18 / 18 / 0 / 0 | N/A; 2385.6 / 3653.2 | 0.03185080 |
| 7: Named-row context, arithmetic, trace repairs | 48 | 18 / 18 / 0 / 0 | 2137.4 / 3276.3; 2451.8 / 3485.5 | 0.09120080 |

Totals: `{"single_turn_attempted": 180, "dialogue_attempted": 125, "dialogue_planned": 126, "dialogue_unattempted": 1, "completed": 304, "errors": 1, "successful_generation_and_review_cost_estimate_usd": 0.36094400000000004, "generation_input_tokens": 547309, "generation_output_tokens": 44569, "claim_review_input_tokens": 153307, "claim_review_output_tokens": 5867}`

- All seven stages reuse non-gold diagnostics; no held-out accuracy claim is available.
- B3 in stages 1 and 2 is reranked; stage 3 uses C2 for the non-reranked hybrid; current B3 disables reranking.
- Historical saved dialogue histories through stage 6 have aliasing; stage 7 has 0/2/4 preceding messages.
- One initial dialogue failed, and its final turn was not attempted: 17 attempts, 16 completed, 1 error, 1 unattempted.
- Latency percentiles include completed responses only. Single-turn runs use two concurrent queries per variant with embedding cache retained; dialogue runs are sequential with cache retained.
- Cost estimates sum successful delivered-response generation plus review; excludes query embedding and uncertain failed-request reservations. Whole-run ledger is larger.
- Do not sum raw_response cost and delivered response cost: delivered response includes runtime-review cost.
- Lexical diagnostics and action-label matches are not semantic accuracy.
- AI semantic reviews are source-grounded agent assessments, not independent human grades; no human accuracy exists.
- Only initial retrieval contrasts and stage 4 paired reranking isolate factors; later fixes were bundled.

All saved summary fields checked against raw rows; mismatches: 0.
Full machine-readable inventory includes per-configuration metrics, token totals, distributions, manifests, hashes and AI review counts: `stage-audit.json`.
