#!/usr/bin/env python3
"""Read completed non-gold results; derive paired, explicitly provisional analysis."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [("B1", "B2", "BM25 to dense retrieval representation"), ("B2", "C1", "fixed to structure-aware chunks"), ("C1", "C2", "dense to hybrid fusion"), ("C2", "B3", "hybrid to hybrid plus reranking")]
METRICS = ["evidence_coverage_5", "evidence_coverage_20", "recall_20", "mrr", "ndcg_10", "provisional_lexical_pass"]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def paired_interval(before, after, *, seed=633, samples=10000):
    before, after = np.asarray(before, dtype=float), np.asarray(after, dtype=float)
    if before.shape != after.shape or before.ndim != 1 or not before.size or not np.isfinite(before).all() or not np.isfinite(after).all():
        raise ValueError("Need finite, nonempty, equally sized paired samples")
    differences = after - before
    indices = np.random.default_rng(seed).integers(0, len(before), (samples, len(before)))
    bounds = np.percentile(differences[indices].mean(axis=1), [2.5, 97.5])
    return {"before_mean": float(before.mean()), "after_mean": float(after.mean()), "difference": float(differences.mean()), "ci95": [float(bounds[0]), float(bounds[1])], "positive_interval": bool(bounds[0] > 0), "negative_interval": bool(bounds[1] < 0), "degenerate": bool(np.all(differences == differences[0])), "paired_denominator": int(len(before)), "seed": seed, "samples": samples}


def covered(unit, chunks):
    intervals = []
    for chunk in chunks:
        if chunk["doc_id"] != unit["doc_id"] or (unit.get("content_hash") and chunk.get("content_hash") != unit["content_hash"]):
            continue
        spans = chunk.get("source_span", chunk.get("source_spans", chunk.get("source_span_json", [])))
        spans = json.loads(spans) if isinstance(spans, str) else spans
        spans = spans.get("spans", [spans]) if isinstance(spans, dict) else spans
        intervals.extend((s["start"], s["end"]) for s in spans if s["end"] > unit["start"] and s["start"] < unit["end"])
    cursor = unit["start"]
    for start, end in sorted(intervals):
        if start > cursor:
            break
        cursor = max(cursor, end)
    return cursor >= unit["end"]


def coverage(item, chunks):
    evidence = item.get("evidence", [])
    return sum(covered(unit, chunks) for unit in evidence) / len(evidence) if evidence else None


def value(row, metric):
    if metric == "provisional_lexical_pass":
        return int(row.get("grade", {}).get("diagnostic_pass", False))
    return row.get("metrics", {}).get(metric)


def pair_metrics(before, after, item_ids, seed, samples):
    result = {}
    for metric in METRICS:
        valid = [identifier for identifier in item_ids if value(before[identifier], metric) is not None and value(after[identifier], metric) is not None]
        excluded = [identifier for identifier in item_ids if identifier not in valid]
        result[metric] = {"item_ids": valid, "excluded_item_ids": excluded, "comparison": paired_interval([value(before[i], metric) for i in valid], [value(after[i], metric) for i in valid], seed=seed, samples=samples) if valid else None}
    return result


def fraction(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator if denominator else None}


def action_summary(rows, items):
    successful = [row for row in rows if "result" in row]
    completed_answerable = [row for row in successful if row["expected_action"] == "answer"]
    expected_refusal = [row for row in successful if row["expected_action"] == "refuse"]
    unanswerable_ids = {i for i, item in items.items() if item.get("category") == "unanswerable"}
    corpus_absent = [row for row in successful if row["item_id"] in unanswerable_ids]
    outcome = lambda row: row["result"]["response"]["action"]
    return {
        "total_items": len(rows), "completed_items": len(successful), "errors": len(rows) - len(successful),
        "expected_actions": dict(Counter(row["expected_action"] for row in rows)),
        "actual_actions_completed": dict(Counter(outcome(row) for row in successful)),
        "provisional_lexical_pass": fraction(sum(value(row, "provisional_lexical_pass") for row in rows), len(rows)),
        "action_agreement": fraction(sum(outcome(row) == row["expected_action"] for row in successful), len(successful)),
        "false_refusal_completed_answerables": fraction(sum(outcome(row) == "refuse" for row in completed_answerable), len(completed_answerable)),
        "answerable_total_including_errors": sum(row["expected_action"] == "answer" for row in rows),
        "expected_refusal_completed": fraction(sum(outcome(row) == "refuse" for row in expected_refusal), len(expected_refusal)),
        "expected_refusal_total_including_errors": sum(row["expected_action"] == "refuse" for row in rows),
        "unanswerable_refusal_completed": fraction(sum(outcome(row) == "refuse" for row in corpus_absent), len(corpus_absent)),
        "unanswerable_total_including_errors": len(unanswerable_ids),
        "unanswerable_definition": "category=unanswerable; separate from safety/adversarial expected refusal",
        "answer_accuracy": None, "semantic_citation_support": None, "grading_status": "HUMAN_REVIEW_PENDING",
    }


def rerank_analysis(rows, items, seed, samples):
    valid, before5, after5, before20, after20 = [], [], [], [], []
    all_latencies = []
    for identifier, row in sorted(rows.items()):
        retrieval = row.get("result", {}).get("retrieval", {})
        latency = retrieval.get("timings", {}).get("rerank_ms")
        if latency is not None:
            all_latencies.append(float(latency))
        if not items[identifier].get("evidence") or "result" not in row:
            continue
        candidates, reranked = retrieval.get("candidates", []), retrieval.get("reranked", [])
        original_ids, reranked_ids = [c["chunk_id"] for c in candidates], [c["chunk_id"] for c in reranked]
        if len(set(original_ids)) != len(original_ids) or len(set(reranked_ids)) != len(reranked_ids):
            raise ValueError("Reranker trace contains duplicate candidate IDs")
        if set(original_ids) != set(reranked_ids):
            raise ValueError("Reranker changed candidate membership; cannot attribute a pure ranking change")
        valid.append(identifier)
        before5.append(coverage(items[identifier], candidates[:5]))
        after5.append(coverage(items[identifier], reranked[:5]))
        before20.append(coverage(items[identifier], candidates[:20]))
        after20.append(coverage(items[identifier], reranked[:20]))
    return {"item_ids": valid,
            "same_request_top5_evidence_change": paired_interval(before5, after5, seed=seed, samples=samples) if valid else None,
            "same_request_pool20_evidence_change": paired_interval(before20, after20, seed=seed, samples=samples) if valid else None,
            "rerank_latency_ms": {"completed_denominator": len(all_latencies), "mean": float(np.mean(all_latencies)) if all_latencies else None, "p50": float(np.percentile(all_latencies, 50)) if all_latencies else None, "p95": float(np.percentile(all_latencies, 95)) if all_latencies else None},
            "latency_note": "Actual saved local stage timing; may include cold model loading and two-query contention. No extra calls.",
            "candidate_pool_limit": "Reordering cannot recover evidence absent from the original 20-candidate pool."}


def validate_variants(variants):
    expected = {"B1": ("bm25", False), "B2": ("dense", False), "C1": ("dense", False), "C2": ("hybrid", False), "B3": ("hybrid", True)}
    for name, (mode, rerank) in expected.items():
        if variants[name].get("mode") != mode or variants[name].get("rerank") is not rerank or not variants[name].get("build_id"):
            raise ValueError(f"Unexpected retrieval configuration for {name}")
    if variants["B1"]["build_id"] != variants["B2"]["build_id"]:
        raise ValueError("B1/B2 must share a chunk build")
    if len({variants[name]["build_id"] for name in ("C1", "C2", "B3")}) != 1:
        raise ValueError("C1/C2/B3 must share a chunk build")
    if variants["B2"]["build_id"] == variants["C1"]["build_id"]:
        raise ValueError("B2/C1 need different builds for the chunking comparison")
    if variants["B0"].get("closed_book") is not True:
        raise ValueError("B0 must be recorded as closed-book")


def analyze(folder, dataset, seed=633, samples=10000):
    folder, dataset = Path(folder).resolve(), Path(dataset).resolve()
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest.get("kind") != "non_gold_diagnostic":
        raise ValueError("Only non_gold_diagnostic runs are permitted; gold/final outputs are excluded")
    if not (folder / "summary.json").exists():
        raise ValueError("Completed summary is absent; wait for the run to finish")
    definitions = jsonl(dataset)
    if any(not item.get("verification_status", "").startswith("diagnostic") for item in definitions):
        raise ValueError("Dataset must be explicitly diagnostic; never read gold or sealed-test data")
    if digest(definitions) != manifest["dataset_hash"]:
        raise ValueError("Dataset hash does not match the recorded run")
    items = {item["item_id"]: item for item in definitions}
    if len(items) != len(definitions):
        raise ValueError("Duplicate diagnostic dataset item IDs")
    variants = {variant["name"]: variant for variant in manifest["configurations"]}
    if len(variants) != len(manifest["configurations"]):
        raise ValueError("Duplicate manifest configuration names")
    required = {"B0", "B1", "B2", "C1", "C2", "B3"}
    if not required <= variants.keys():
        raise ValueError("Run needs B0/B1/B2/C1/C2/B3 for controlled comparisons")
    validate_variants(variants)
    rows = jsonl(folder / "results.jsonl")
    groups = {name: {} for name in required}
    for row in rows:
        if row["configuration"] not in groups:
            continue
        group = groups[row["configuration"]]
        if row["item_id"] in group:
            raise ValueError("Duplicate configuration/item results; do not cherry-pick a retry")
        group[row["item_id"]] = row
    expected_ids = set(items)
    for name, group in groups.items():
        if set(group) != expected_ids:
            raise ValueError(f"Incomplete or mismatched item IDs for {name}")
        if any(row["expected_action"] != items[identifier]["expected_action"] for identifier, row in group.items()):
            raise ValueError("Expected action changed between dataset and results")
    ids = sorted(items)
    observed_models = {row["result"]["response"].get("model") for name, group in groups.items() if name != "B0" for row in group.values() if "result" in row}
    if len(observed_models) > 1 or None in observed_models:
        raise ValueError("Completed RAG variants must record one shared generator model")
    pairs = {}
    for before, after, factor in PAIRS:
        pairs[f"{before}->{after}"] = {"factor": factor, "configurations": {before: variants[before], after: variants[after]}, "metrics": pair_metrics(groups[before], groups[after], ids, seed, samples)}
    b0_incorrect = [i for i in ids if items[i]["expected_action"] == "answer" and not value(groups["B0"][i], "provisional_lexical_pass") and "result" in groups["B0"][i]]
    report = {
        "kind": "PAIRED_NON_GOLD_DIAGNOSTIC_ANALYSIS", "run": str(folder), "dataset": str(dataset),
        "results_sha256": hashlib.sha256((folder / "results.jsonl").read_bytes()).hexdigest(), "dataset_hash": manifest["dataset_hash"], "config_hash": manifest["config_hash"],
        "total_items_per_configuration": len(ids), "seed": seed, "samples": samples,
        "controlled_configuration_checks": {"recorded_build_and_modes_validated": True, "generator_models_observed": sorted(observed_models), "template_and_corpus_identity": "Shared recorded config hash; full per-request prompt hashes include different retrieved contexts. Build contents/template snapshots must be reviewed separately."},
        "limits": ["AI-authored diagnostic labels are unverified; semantic answer accuracy/citation support remain unknown.", "Lexical pass is the saved action/fact-word-overlap/guard heuristic, not semantic correctness; paraphrases can fail it.", "Metric intervals resample exact paired item IDs. These exploratory intervals do not adjust for multiple comparisons or annotation uncertainty.", "Chunk-level relevance denominators change after re-chunking; immutable-source evidence coverage complements them.", "Provider errors remain visible; missing numeric metrics are excluded with IDs, while lexical error outcomes count as failures.", "B0 provisional subset uses completed answerable items failing the lexical diagnostic, not demonstrated prior-knowledge errors."],
        "pairs": pairs, "actions": {name: action_summary(list(group.values()), items) for name, group in sorted(groups.items())},
        "reranking": rerank_analysis(groups["B3"], items, seed, samples),
        "b0_incorrect_provisional_subset": {"item_ids": b0_incorrect, "denominator": len(b0_incorrect), "b0_provider_errors_excluded": [i for i in ids if items[i]["expected_action"] == "answer" and "error" in groups["B0"][i]], "metric_by_configuration": {name: {metric: {"mean": float(np.mean(values)) if values else None, "denominator": len(values)} for metric in METRICS for values in [[value(group[i], metric) for i in b0_incorrect if value(group[i], metric) is not None]]} for name, group in sorted(groups.items())}},
        "answer_accuracy": None, "semantic_citation_support": None, "human_review_status": "HUMAN_REVIEW_PENDING",
    }
    return report


def markdown(report):
    lines = ["# Paired non-gold diagnostic analysis", "", f"Run: `{report['run']}`. Items per configuration: {report['total_items_per_configuration']}.", "", "All lexical outcomes are provisional diagnostic signals. Human semantic accuracy and citation support remain unknown.", "", "| Pair | Metric | Paired n | Before | After | Difference | Paired 95% interval |", "| --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for pair, payload in report["pairs"].items():
        for metric, data in payload["metrics"].items():
            result = data["comparison"]
            if result:
                low, high = result["ci95"]
                lines.append(f"| {pair} | {metric} | {result['paired_denominator']} | {result['before_mean']:.3f} | {result['after_mean']:.3f} | {result['difference']:+.3f} | [{low:+.3f}, {high:+.3f}] |")
    lines += ["", "Intervals including zero are inconclusive. A positive or negative interval describes these diagnostic observations only; no human-reviewed course improvement is established.", "", "## Action outcomes", "", "| Variant | Completed/total | Action agreement | False refusals/answerables | Unanswerable refusals | Expected refusals (all reasons) | Errors |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    label = lambda result: f"{result['numerator']}/{result['denominator']}" if result["denominator"] else "N/A (0 items)"
    for name, data in report["actions"].items():
        lines.append(f"| {name} | {data['completed_items']}/{data['total_items']} | {label(data['action_agreement'])} | {label(data['false_refusal_completed_answerables'])} | {label(data['unanswerable_refusal_completed'])} | {label(data['expected_refusal_completed'])} | {data['errors']} |")
    lines += ["", "## Same-request reranking", "", "```json", json.dumps(report["reranking"], indent=2), "```", "", f"B0-incorrect **provisional lexical** subset: {report['b0_incorrect_provisional_subset']['denominator']} completed answerable items. Exact IDs and variant metrics are in analysis.json; this is not a semantic knowledge baseline.", "", "## Limits", ""]
    lines.extend(f"- {limit}" for limit in report["limits"])
    return "\n".join(lines) + "\n"


def self_test():
    paired = paired_interval([0, 1], [1, 0], samples=1000)
    assert paired["difference"] == 0 and paired["ci95"] == [-1.0, 1.0]
    assert paired_interval([1, 1], [1, 1], samples=1000)["degenerate"]
    unit = {"doc_id": "synthetic", "content_hash": "h", "start": 0, "end": 10}
    chunks = [{"doc_id": "synthetic", "content_hash": "h", "source_span": [{"start": 0, "end": 5}]}, {"doc_id": "synthetic", "content_hash": "h", "source_span": [{"start": 5, "end": 10}]}]
    assert covered(unit, chunks) and not covered(unit, chunks[:1])
    assert not covered(dict(unit, content_hash="different"), chunks)
    print("Pure synthetic analysis self-checks passed; no files or provider calls.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_folder", nargs="?")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/evaluation/diagnostic.jsonl")
    parser.add_argument("--seed", type=int, default=633)
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.run_folder or args.samples < 1:
        parser.error("A completed diagnostic run folder and positive sample count are required")
    report = analyze(args.run_folder, args.dataset, args.seed, args.samples)
    destination = Path(args.run_folder) / ("analysis-" + digest({"results": report["results_sha256"], "seed": args.seed, "samples": args.samples, "script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})[:12])
    destination.mkdir(exist_ok=True)
    for name, text in [("analysis.json", json.dumps(report, indent=2) + "\n"), ("analysis.md", markdown(report))]:
        path = destination / name
        if path.exists():
            if path.read_text() != text:
                raise ValueError("Existing analysis differs; do not overwrite it")
        else:
            with path.open("x") as stream:
                stream.write(text)
    print(json.dumps({"analysis_folder": str(destination.resolve()), "items_per_variant": report["total_items_per_configuration"], "human_review_status": report["human_review_status"]}, indent=2))


if __name__ == "__main__":
    main()
