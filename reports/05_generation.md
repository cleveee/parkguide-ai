# Generation and actual conversations

These are implementation reports. Gold verification, semantic grading, and the final held-out benchmark remain subject to real human review. Diagnostic scores are not assignment-valid gold accuracy.

The provider uses structured claim objects, allowed source IDs, temperature zero, and an explicit source-only prompt. B0 has a documented closed-book exception. Response rendering uses trusted URLs. Guards block unknown IDs, unsupported numerical witnesses, generated URLs, and more than 25 consecutive copied words per source page. These guards do not prove semantic support; separate review is required.

Actual conversation run:

```json
{
  "folder": "/Users/robin/Build/Personal/parkguide-ai/artifacts/dialogues/7bbd1b0ccdb649edbaf2b64ccc9797e3",
  "dialogues": 6,
  "attempted_turns": 18,
  "actual_turns": 18,
  "errors": 0,
  "grading_status": "HUMAN_REVIEW_PENDING"
}
```

History uses actual previous assistant responses and fresh factual retrieval. Search traces include filters and pre/post scores. Source dates are snapshot metadata, not proof of current safety.

An optional independent AI claim reviewer checks each assertion against its cited passages and withholds unsupported claims. It uses the same approved model with a separate prompt and budgeted request. This improves inspection but does not prove entailment; human calibration remains required. Saved traces include all original claims and reviewer decisions. See docs/CLAIM_REVIEW.md.

Explicit table requests filter to captured table-bearing pages. Named-row context packing retains the source row within the candidate pool without altering recorded rankings. Difference questions can use a deterministic Decimal calculation from named rows, explicit header units, and immutable source cells; derived values have an equation/operand trace and pass the same citation/review guards. The original model output is preserved. Per-turn histories are now snapshots; earlier immutable dialogue artifacts have a documented mutable-trace alias limitation.

## Current Azure-only park selector update

Robin's October 10 instruction replaces the original generator with Azure Luna on the existing embedding resource. The one endpoint/key serves text-embedding-3-small and the gpt-6-luna deployment, returning pinned gpt-6-luna-2026-09-22. Selected-park UI answers require reviewed source witnesses; its default reranker is on. Earlier conversation pointers and metrics above describe historical GPT-4 diagnostics and are not replayed or regraded on Luna. See docs/GENERATION.md, docs/PARK_SCOPE.md and the dashboard for the actual new attempts.
