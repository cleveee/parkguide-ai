"""Generate the concise matrix report from frozen labels and actual responses."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path

from gold_matrix import CONFIGS, DATA, ROOT, RUN, dump, readlines, sha, utc


def pct(value):
    return f"{100*value:.1f}%" if value is not None else "N/A"


def main():
    metrics = json.loads((RUN / "metrics.json").read_text())
    semantic = json.loads((RUN / "semantic-summary.json").read_text())
    botmeta = json.loads((RUN / "chatbot/metadata.json").read_text())
    consensus = json.loads((DATA / "consensus-manifest.json").read_text())
    rows = readlines(DATA / "gold-consensus.jsonl")
    action = metrics["action_metrics"]
    retrieval = metrics["retrieval_metrics"]
    agreement = metrics["agreement"]
    operational = metrics["operational"]
    matrix_rows, claude_cost = [], 0
    for name, config in CONFIGS.items():
        directory = RUN / "reviewers" / name
        labels = json.loads((directory / "labels.json").read_text())["labels"]
        provenance = json.loads((directory / "provenance.json").read_text())
        validation = json.loads((directory / "source-validation.json").read_text())
        model = ", ".join((provenance.get("model_usage") or {}).keys()) or config["model"] + " (configured)"
        cost = provenance.get("total_cost_usd")
        if cost is not None: claude_cost += cost
        represented = agreement["consensus_fact_representation"][name]
        matrix_rows.append(f"| [{name}](../artifacts/gold-matrix-v1/reviewers/{name}/labels.raw.json) | {model} / {config['effort']} | 40 | {sum(len(r['required_facts']) for r in labels)} | {validation['quotes']} | {represented['represented']}/{represented['total']} |")
    action_rows = [f"| {r['class']} | {r['support']} | {r['tp']} / {r['fp']} / {r['fn']} | {pct(r['precision'])} | {pct(r['recall'])} | {pct(r['f1'])} |" for r in action["per_class"]]
    retrieval_rows = []
    for k in [5, 20]:
        r = retrieval[f"at_{k}"]
        retrieval_rows.append(f"| Ranked chunks @{k} | {r['items']} | {r['tp']}/{r['retrieved']} | {r['tp']}/{r['known_relevant']} | {pct(r['micro_precision'])} | {pct(r['micro_recall'])} | {pct(r['micro_f1'])} |")
    categories = Counter(r["category"] for r in rows)
    single_page_multihop = [r["candidate_item_id"] for r in rows if r["category"] == "multi_hop" and len({ev["doc_id"] for f in r["required_facts"] for group in f["evidence_groups"] for ev in group}) < 2]
    dump(RUN / "dataset-audit.json", {"cases": len(rows), "unique_ids": len({r["item_id"] for r in rows}), "selected_park_counts": dict(Counter(r["selected_park"] for r in rows)), "category_lineage_counts": dict(categories), "multi_hop_lineage_with_single_page_reference": single_page_multihop, "category_note": "Category labels preserve original candidate lineage; independent source consensus can collapse a presumed multi-hop case to one page.", "human_verified": False})
    failures = {r["item_id"]: r for r in json.loads((RUN / "semantic-assessment.json").read_text())["assessments"]}
    per_items = {r["item_id"]: r for r in readlines(RUN / "per-item-metrics.jsonl")}
    failure_lines = []
    for ref in rows:
        item_id = ref["item_id"]
        if item_id not in semantic["not_full_pass_item_ids"]: continue
        judged = failures[item_id]
        details = []
        if not per_items[item_id]["action_correct"]: details.append(f"expected {ref['action']}, received {per_items[item_id]['actual_action']}")
        fact_problems = [f for f in judged["facts"] if f["status"] != "covered"]
        if fact_problems and per_items[item_id]["action_correct"]:
            details.append(f"{len(fact_problems)}/{len(judged['facts'])} required facts not delivered: {fact_problems[0]['reason']}")
        details += [b["reason"] for b in judged["behaviors"] if b["status"] != "satisfied"]
        details += [c["reason"] for c in judged["claims"] if c["status"] != "supported"]
        details += [x["reason"] for x in judged["additional_answer_issues"]]
        failure_lines.append(f"| {item_id} / {ref['candidate_item_id']} | {'; '.join(dict.fromkeys(details)).replace('|',' / ')} |")
    delta = botmeta["budget_after"]["estimated_committed_usd"] - botmeta["budget_before"]["estimated_committed_usd"]
    disagreements = [r["item_id"] for r in rows if r["disagreements"]]
    document = f"""# Eval

Five independent configurations produced a source-backed consensus for 40 questions. Fresh chatbot responses achieved **{round(action['accuracy']*40)}/40 correct actions** and **{semantic['full_rubric_pass']['passed']}/40 full rubric passes**. References and semantic grades remain AI provisional; human review is pending.

## Results

| Measurement | Result |
| --- | ---: |
| Fresh calls completed / attempted | {operational['completed']}/{operational['attempted']} ({operational['errors']} execution errors) |
| Correct action | {round(action['accuracy']*40)}/40 |
| Action micro precision / recall / F1 | {pct(action['micro_precision'])} / {pct(action['micro_recall'])} / {pct(action['micro_f1'])} |
| Action macro precision / recall / F1 | {pct(action['macro_precision'])} / {pct(action['macro_recall'])} / {pct(action['macro_f1'])} |
| Required facts delivered, AI assessed | {semantic['facts'].get('covered',0)}/{semantic['fact_total']} ({pct(semantic['required_fact_coverage'])}) |
| Behavior requirements satisfied, AI assessed | {semantic['behaviors'].get('satisfied',0)}/{semantic['behavior_total']} ({pct(semantic['behavior_satisfaction'])}) |
| Delivered claims with valid citation identity | {semantic['claim_citation_identity_valid']['valid']}/{semantic['claim_total']} |
| Delivered claims supported by cited passages, AI assessed | {semantic['delivered_claims'].get('supported',0)}/{semantic['claim_total']} ({pct(semantic['claim_citation_semantic_support'])}) |
| Full rubric pass, AI assessed | {semantic['full_rubric_pass']['passed']}/40 |
| End-to-end latency p50 / p95 | {operational['latency_p50_ms']/1000:.2f}s / {operational['latency_p95_ms']/1000:.2f}s |

Semantic figures come from one AI assessor and have not been calibrated against human grades.

| Action | Expected cases | TP / FP / FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(action_rows)}

| Retrieval | Scorable cases | Hits / retrieved | Hits / known relevant | Micro precision | Micro recall | Micro F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(retrieval_rows)}

Required-fact evidence coverage is {pct(retrieval['at_5']['fact_evidence_coverage'])} at five ranked chunks and {pct(retrieval['at_20']['fact_evidence_coverage'])} at 20. Coverage in the actual generation contexts is {pct(retrieval['generation_context_fact_evidence_coverage']['mean'])} across {retrieval['generation_context_fact_evidence_coverage']['denominator']} answerable cases. MRR is {retrieval['mrr']['mean']:.3f}; nDCG@10 is {retrieval['ndcg_at_10']['mean']:.3f}. Zero-known-qrel items excluded from chunk recall aggregates: {', '.join(retrieval['missing_qrels_items']) or 'none'}.

## Independent labeling matrix

| Labeler | Model / effort | Labels | Proposed facts | Exact quotes checked | Consensus facts represented |
| --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(matrix_rows)}

All five chose 30 answers, eight refusals, and two clarifications. Pairwise action agreement, leave-one-out action F1 and Fleiss κ are 1.000. These measure agreement, not correctness. Fact representation measures overlap with the derived reference; labelers split and qualify facts differently.

The [consensus dataset](../data/evaluation/gold-matrix-v1/gold-consensus.jsonl) has {consensus['facts']} atomic facts, derived from all five outputs with equal action votes and semantic fact grouping. Facts need three supporters, except a documented source-critical override on {', '.join(consensus['source_overrides']) or 'none'}. Raw labels, votes and fact-detail disagreements on {len(disagreements)} cases are retained. A gpt-6-sol/high adjudicator saw no chatbot outputs; a separate gpt-5.6-sol/high assessor graded responses. A [late evidence supplement](../artifacts/gold-matrix-v1/freeze-incident.json) for M005 is retained separately; scores use the original frozen reference. Codex runtime identities/tokens/costs are unknown; its configurations are recorded. Claude identities and usage come from CLI responses.

## Cases to improve

| Case | Provisional finding |
| --- | --- |
{chr(10).join(failure_lines) if failure_lines else '| — | All cases satisfy the provisional rubric. |'}

These cases form the next targeted regression checks. They were retained in the scores; no answer-quality retries or post-response reference changes were made. Guard events are recorded separately: {', '.join(operational['guard_error_item_ids']) or 'none'}. Uncertain semantic cases: {', '.join(semantic['uncertain_item_ids']) or 'none'}.

## Scope and interpretation

All 40 questions come from revised `data/evaluation` candidates. Four cross-park comparisons became within-park comparisons; every request supplies one selected park and empty history. Category lineage: {', '.join(f'{k} {v}' for k,v in sorted(categories.items()))}. Of six presumed multi-hop cases, {6-len(single_page_multihop)} use multiple pages; {', '.join(single_page_multihop) or 'none'} resolves from one page. Tables, exceptions, dates, source limits and injection are included. Extra scope controls and six dialogue candidates in the [functionality audit](../docs/EVALUATION_FUNCTIONALITY.md) are outside this run.

The packet contains 30 saved NPS documents and a 155-document inventory. Source selection used earlier candidate evidence: this is a development diagnostic with prior exposure, not a held-out benchmark or exhaustive absence search. Human verification remains pending; the original course gold seal is unchanged.

Calls used local `chat.answer` at [commit {botmeta['code_commit'][:7]}](https://github.com/cleveee/parkguide-ai/commit/{botmeta['code_commit']}), hybrid retrieval, no reranker and the pinned Luna snapshot. Settings match the hosted profile; execution and latency are local, without Vercel/UI testing. Responses are fresh; embeddings may use existing cache. The shared Azure ledger increased by ${delta:.6f} estimated cost, not isolated billing. Claude reports ${claude_cost:.6f} separately; Codex costs are unknown.

Precision is TP/(TP+FP), recall is TP/(TP+FN), and F1 is their harmonic mean. Action macro scores average the three classes; micro scores aggregate counts. Failed calls would remain incorrect predictions. [Scikit-learn metric definitions](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_fscore_support.html)

A relevant chunk must fully cover an evidence group for one required fact. @5/@20 use ranked candidates before context pruning; precision divides by actual returned count. Qrels cover declared evidence alternatives, not exhaustive human relevance; group coverage differs from older evidence-unit metrics. Citation support divides by delivered claims. Rejected-candidate precision/recall/F1 are unavailable without a labeled candidate universe. The saved-case approach follows the [OpenAI evaluation guide](https://developers.openai.com/api/docs/guides/evals).

## Artifacts and reproduction

[Result manifest](../artifacts/gold-matrix-v1/result-manifest.json) · [Metrics](../artifacts/gold-matrix-v1/metrics.json) · [Per-case metrics](../artifacts/gold-matrix-v1/per-item-metrics.jsonl) · [Agreement](../artifacts/gold-matrix-v1/agreement.json) · [Qrels](../artifacts/gold-matrix-v1/qrels.json) · [Fresh responses](../artifacts/gold-matrix-v1/chatbot/responses.jsonl) · [Semantic assessments](../artifacts/gold-matrix-v1/semantic-assessment.json) · [Frozen consensus adjudication](../artifacts/gold-matrix-v1/adjudication.frozen.json) · [Independent metric review](../artifacts/gold-matrix-v1/metrics-review-final.json) · [Report review](../artifacts/gold-matrix-v1/report-review.json)

Run from the repository with its existing environment; these commands make no model calls:

```sh
.venv/bin/python scripts/derive_gold_matrix.py score
.venv/bin/python scripts/assess_gold_matrix.py summarize
.venv/bin/python scripts/build_gold_matrix_report.py
```

Raw labels, responses and the consensus are never overwritten by these commands. Aggregate generation timestamps may change; counts and scores reproduce from the saved inputs. Preparation, validation and optional **new paid runs** are separated in [gold_matrix.py](../scripts/gold_matrix.py). The earlier [18-question labeling study](../docs/AI_LABELING_SAMPLE.md) and [retrospective hallucination pilot](hallucination-experiment-20261010/REPORT.md) are separate datasets and are not added to this run's denominators.
"""
    report = ROOT / "reports/GOLD_MATRIX_EVALUATION.md"
    report.parent.mkdir(exist_ok=True)
    report.write_text(document)
    paths = list(DATA.rglob("*")) + list(RUN.rglob("*")) + [ROOT / "scripts" / name for name in ["gold_matrix.py", "derive_gold_matrix.py", "assess_gold_matrix.py", "build_gold_matrix_report.py"]] + [report]
    manifest = {"created_at": utc(), "status": "COMPLETED_AI_PROVISIONAL_HUMAN_REVIEW_PENDING", "labelers": CONFIGS,
                "additional_worker_configurations": {"source_adjudicator": {"model": "gpt-6-sol", "effort": "high"}, "metric_reviewer": {"model": "gpt-5.6-luna", "effort": "high"}, "semantic_assessor": {"model": "gpt-5.6-sol", "effort": "high"}},
                "labels": 200, "reference_cases": 40, "fresh_attempts": 40, "execution_errors": operational["errors"],
                "source_code_commit": botmeta["code_commit"], "build_id": botmeta["build_id"],
                "database_sha256": sha(ROOT / "data/parkguide.sqlite"), "original_gold_sha256": sha(ROOT / "data/evaluation/gold-drafts.jsonl"),
                "claude_cli_reported_total_usd": claude_cost, "azure_shared_ledger_interval_estimate_usd": delta,
                "codex_cost_usd": None, "human_verified": False, "benchmark_eligible": False,
                "artifacts_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths) if p.is_file() and p.name not in ["result-manifest.json", "workspaces.local.json"]}}
    dump(RUN / "result-manifest.json", manifest)
    print(json.dumps({"report": str(report), "artifact_hashes": len(manifest["artifacts_sha256"])}))


if __name__ == "__main__": main()
