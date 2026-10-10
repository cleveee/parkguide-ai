# Provisional conversation uncertainty

The final saved six-dialogue diagnostic has **16 clearly correct turns out of all 18 attempted turns**, plus two uncertain turns and zero clearly incorrect turns under the source-based **AI review**. The uncertain turns, T02/1 and T05/3, remain in the denominator. They are not counted correct or relabeled incorrect. These are development diagnostics with human verification pending, not course gold accuracy.

| Observed AI judgment | Numerator / total | Fraction | 95% dialogue-cluster bootstrap interval |
| --- | ---: | ---: | --- |
| Clearly correct delivered turns | 16/18 | 88.9% | [77.8%, 100.0%] |
| Supported delivered factual claims | 21/23 | 91.3% | [81.8%, 100.0%] |

The 23 delivered claims include **21 supported, one unsupported and one uncertain** AI claim judgment. Both remaining claims stay in the denominator. A turn-level uncertain judgment and a claim-level unsupported judgment are different units; the script preserves the source review's labels. Refusal and clarification turns can be clearly correct without supplying factual claims.

| Dialogue | Clearly correct / turns | Uncertain turns | Supported / delivered claims | Unsupported claims | Uncertain claims |
| --- | ---: | ---: | ---: | ---: | ---: |
| T01 | 3/3 | 0 | 3/3 | 0 | 0 |
| T02 | 2/3 | 1 | 2/3 | 0 | 1 |
| T03 | 3/3 | 0 | 4/4 | 0 | 0 |
| T04 | 3/3 | 0 | 4/4 | 0 | 0 |
| T05 | 2/3 | 1 | 5/6 | 1 | 0 |
| T06 | 3/3 | 0 | 3/3 | 0 | 0 |

The script verified all 18 unique reviewed turn IDs against their actual delivered responses and artifact hash. All six saved histories contain only actual preceding user/assistant turns, and the run has zero pipeline errors. Those integrity checks do not certify semantic correctness.

## Reproduce the saved analysis

Input review: [latest-semantic-review.jsonl](/Users/robin/Build/Personal/parkguide-ai/artifacts/reviews/latest-semantic-review.jsonl), SHA256 `4ba4836a0275ec7940e61287c2fdd4dc1af7e4c67d4de1b8068776372f4e4d0c`. It contains 66 total reviewed rows; this analysis selects only the 18 dialogue rows. The paired single-turn experiments remain separate.

Actual dialogue run: `7bbd1b0ccdb649edbaf2b64ccc9797e3`, with result SHA256 `77aeeeb943a12a704d84f8d86dfe2246db43c6479fb28b224d64fe7d21cad2a3`.

```sh
.venv/bin/python scripts/analyze_conversations.py --self-test
.venv/bin/python scripts/analyze_conversations.py \
  --dialogue-folder artifacts/dialogues/7bbd1b0ccdb649edbaf2b64ccc9797e3 \
  --expected-review-sha 4ba4836a0275ec7940e61287c2fdd4dc1af7e4c67d4de1b8068776372f4e4d0c
```

The immutable derived [conversation-analysis.json](/Users/robin/Build/Personal/parkguide-ai/artifacts/dialogues/7bbd1b0ccdb649edbaf2b64ccc9797e3/conversation-analysis-60f2c3fb3b8b/conversation-analysis.json) records the review/result/manifest hashes, exact item IDs, counts, labels, seed, draws and limits. Output lives in an ignored content-addressed subfolder. The script makes no API calls and never edits source reviews, core code, gold data or original results.

## What the interval means

With seed 633 and 10,000 draws, each bootstrap draw samples **six whole dialogues with replacement**. Every chosen dialogue retains all three turns and all its delivered claims. The statistic divides the summed clear/supported counts by the summed relevant total; it does not independently resample turns or average dialogue claim fractions with unequal claim counts.

The intervals describe sampling variation of the fixed AI labels under dialogue resampling. They do **not** account for judge mistakes, source-label ambiguity, annotation uncertainty or a new held-out test. Six authored development dialogues are a small, non-random set. Human answer accuracy and semantic citation support remain unknown; the script records both as null. No before/after causal improvement or final acceptance is claimed.

The observed conservative fractions remain below the proposed 90% clear-turn and 95% claim-support gates, and those gates additionally require actual human review. Their upper interval endpoints do not turn an unmet gate into a pass. Preserve the two uncertain cases for human source interpretation and retain the unsupported claim as an observed AI concern.
