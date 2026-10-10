#!/usr/bin/env python3
"""Analyze completed B3/R1 diagnostic outputs without provider or gold access."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from analyze_diagnostics import action_summary, coverage, digest, jsonl, pair_metrics, paired_interval, rerank_analysis

ROOT = Path(__file__).resolve().parents[1]


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_completed(folder, dataset, names):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest.get("kind") != "non_gold_diagnostic" or not (folder / "summary.json").exists():
        raise ValueError("Only completed non-gold diagnostic runs are permitted")
    if digest(dataset) != manifest["dataset_hash"]:
        raise ValueError("Diagnostic dataset hash does not match the run")
    variants = {v["name"]: v for v in manifest["configurations"]}
    if len(variants) != len(manifest["configurations"]) or not set(names) <= variants.keys():
        raise ValueError("Missing or duplicate recorded configurations")
    items = {item["item_id"]: item for item in dataset}
    groups = {name: {} for name in names}
    for row in jsonl(folder / "results.jsonl"):
        if row["configuration"] not in groups:
            continue
        group = groups[row["configuration"]]
        if row["item_id"] in group:
            raise ValueError("Duplicate item/configuration; do not cherry-pick retries")
        group[row["item_id"]] = row
    for name, group in groups.items():
        if set(group) != set(items):
            raise ValueError(f"Incomplete or different item IDs in {name}")
        for identifier, row in group.items():
            if row["expected_action"] != items[identifier]["expected_action"]:
                raise ValueError("Expected action changed in saved outputs")
            if "result" in row and row["result"].get("config_hash") != manifest["config_hash"]:
                raise ValueError("Saved response configuration differs from its run manifest")
    return folder, manifest, variants, groups


def chunk_identity(chunks):
    return [(c["chunk_id"], c["doc_id"], c.get("content_hash"), c["text"], c.get("source_span", c.get("source_span_json"))) for c in chunks]


def validate_pair(variants, groups):
    before, after = variants["B3"], variants["R1"]
    if before.get("mode") != "hybrid" or after.get("mode") != "hybrid" or before.get("rerank") is not False or after.get("rerank") is not True or before.get("build_id") != after.get("build_id"):
        raise ValueError("B3/R1 must share a hybrid build and differ only in rerank")
    models, checked, failed, preflight = set(), [], [], []
    for identifier in sorted(groups["B3"]):
        left, right = groups["B3"][identifier], groups["R1"][identifier]
        if "result" not in left or "result" not in right:
            failed.append(identifier)
            continue
        a, b = left["result"], right["result"]
        for field in ("question", "history", "retrieval_query", "filters", "closed_book", "config_hash"):
            if a.get(field) != b.get(field):
                raise ValueError(f"B3/R1 changed {field} for {identifier}")
        ar, br = a["retrieval"], b["retrieval"]
        ac, bc = ar.get("candidates", []), br.get("candidates", [])
        if chunk_identity(ac) != chunk_identity(bc):
            raise ValueError(f"B3/R1 original candidate order/content differs for {identifier}")
        if len(ac) > 20 or len({c["chunk_id"] for c in ac}) != len(ac):
            raise ValueError("Original candidate pool must contain at most 20 unique chunks")
        post = br.get("reranked", [])
        if len(post) != len(bc) or {c["chunk_id"] for c in post} != {c["chunk_id"] for c in bc}:
            raise ValueError("R1 reranking changed candidate membership")
        if sorted(chunk_identity(post)) != sorted(chunk_identity(bc)):
            raise ValueError("R1 reranking changed source content or evidence metadata")
        if ac:
            if ar.get("build_id") != before["build_id"] or br.get("build_id") != after["build_id"]:
                raise ValueError("Actual retrieval build differs from recorded pair")
            if [c["chunk_id"] for c in ar.get("reranked", ac)] != [c["chunk_id"] for c in ac]:
                raise ValueError("Selected B3 must preserve the original candidate ordering")
        for result in (a, b):
            response = result["response"]
            if response.get("preflight_reason") and not response.get("usage") and response.get("elapsed_ms") == 0:
                if identifier not in preflight:
                    preflight.append(identifier)
            else:
                models.add(response.get("model"))
        checked.append(identifier)
    if len(models) > 1 or None in models:
        raise ValueError("Completed paired responses must share one recorded generator model")
    return {"completed_paired_item_ids": checked, "provider_or_pipeline_errors_excluded": failed, "generator_models": sorted(models), "local_preflight_without_generator_item_ids": preflight, "original_candidate_order_content_and_query_match": True, "shared_build": before["build_id"], "prompt_control_note": "Shared recorded config/code hashes; full request hashes include differing retrieved context. No unrecorded template identity is inferred."}


def latency_value(row, metric):
    result = row.get("result", {})
    if metric == "end_to_end_ms":
        return result.get("elapsed_ms")
    if metric == "generation_ms":
        return result.get("response", {}).get("elapsed_ms")
    return result.get("retrieval", {}).get("timings", {}).get(metric)


def latency_analysis(before, after, ids, seed, samples):
    report = {}
    for metric in ("end_to_end_ms", "generation_ms", "load_ms", "retrieval_ms", "rerank_ms", "total_ms"):
        valid = [i for i in ids if latency_value(before[i], metric) is not None and latency_value(after[i], metric) is not None]
        a = [latency_value(before[i], metric) for i in valid]
        b = [latency_value(after[i], metric) for i in valid]
        report[metric] = {"paired_item_ids": valid, "excluded_item_ids": [i for i in ids if i not in valid], "comparison": paired_interval(a, b, seed=seed, samples=samples) if valid else None,
                          "before_p50": float(np.percentile(a, 50)) if a else None, "after_p50": float(np.percentile(b, 50)) if b else None, "before_p95": float(np.percentile(a, 95)) if a else None, "after_p95": float(np.percentile(b, 95)) if b else None}
    executing = [i for i in ids if before[i].get("result", {}).get("retrieval", {}).get("candidates") and after[i].get("result", {}).get("retrieval", {}).get("candidates")]
    report["end_to_end_retrieval_executed_ms"] = {"paired_item_ids": executing, "excluded_item_ids": [i for i in ids if i not in executing], "comparison": paired_interval([latency_value(before[i], "end_to_end_ms") for i in executing], [latency_value(after[i], "end_to_end_ms") for i in executing], seed=seed, samples=samples) if executing else None}
    return report


def bundled_changes(initial, current, ids, seed, samples):
    output = {"scope": "Initial C2 to current selected B3: bundled prompt/history/guard corrections and generation variability; not a causal retrieval comparison", "metrics": {}}
    for metric in ("action_agreement", "provisional_lexical_pass"):
        def outcome(row):
            if metric == "action_agreement":
                return int(row.get("result", {}).get("response", {}).get("action") == row["expected_action"])
            return int(row.get("grade", {}).get("diagnostic_pass", False))
        a, b = [outcome(initial[i]) for i in ids], [outcome(current[i]) for i in ids]
        output["metrics"][metric] = {"paired_item_ids": ids, "comparison": paired_interval(a, b, seed=seed, samples=samples), "improved_ids": [i for i, x, y in zip(ids, a, b) if y > x], "worsened_ids": [i for i, x, y in zip(ids, a, b) if y < x], "error_outcomes_count_as_failures": True}
    return output


def analyze(current_folder, initial_folder, dataset_path, seed=633, samples=10000):
    definitions = jsonl(dataset_path)
    if not definitions or any(not item.get("verification_status", "").startswith("diagnostic") for item in definitions):
        raise ValueError("Only explicitly diagnostic definitions are permitted; no gold access")
    items = {item["item_id"]: item for item in definitions}
    if len(items) != len(definitions):
        raise ValueError("Duplicate diagnostic item IDs")
    current, manifest, variants, groups = read_completed(current_folder, definitions, ("B3", "R1"))
    initial, old_manifest, old_variants, old_groups = read_completed(initial_folder, definitions, ("C2",))
    checked = validate_pair(variants, groups)
    ids = sorted(items)
    numeric = pair_metrics(groups["B3"], groups["R1"], ids, seed, samples)
    pool = []
    for identifier in ids:
        left, right = groups["B3"][identifier], groups["R1"][identifier]
        if "result" not in left or "result" not in right or not items[identifier].get("evidence"):
            continue
        candidates = right["result"]["retrieval"].get("candidates", [])
        pool.append({"item_id": identifier, "original_candidate_count": len(candidates), "original_candidate_recall_20": left.get("metrics", {}).get("recall_20"), "post_rerank_recall_20": right.get("metrics", {}).get("recall_20"), "original_source_evidence_coverage_20": coverage(items[identifier], candidates[:20]), "post_source_evidence_coverage_20": coverage(items[identifier], right["result"]["retrieval"].get("reranked", candidates)[:20])})
    action = {name: action_summary(list(group.values()), items) for name, group in groups.items()}
    changes = bundled_changes(old_groups["C2"], groups["B3"], ids, seed, samples)
    changes["initial_C2_actions"] = action_summary(list(old_groups["C2"].values()), items)
    changes["current_B3_actions"] = action["B3"]
    paths = {"current_manifest": current / "manifest.json", "current_results": current / "results.jsonl", "initial_manifest": initial / "manifest.json", "initial_results": initial / "results.jsonl", "diagnostic_dataset": Path(dataset_path).resolve()}
    return {"kind": "CURRENT_CANDIDATE_NON_GOLD_ANALYSIS", "current_run": str(current), "initial_run": str(initial), "dataset_hash": manifest["dataset_hash"], "input_sha256": {name: file_hash(path) for name, path in paths.items()}, "seed": seed, "samples": samples, "items_per_variant": len(ids),
            "current_config_hash": manifest["config_hash"], "current_code_hash": manifest.get("code_hash"), "initial_config_hash": old_manifest["config_hash"], "initial_code_hash": old_manifest.get("code_hash"), "current_configurations": variants, "initial_C2_configuration": old_variants["C2"], "paired_controls": checked,
            "B3_to_R1_paired_metrics": numeric, "B3_to_R1_paired_action_agreement": bundled_changes(groups["B3"], groups["R1"], ids, seed, samples)["metrics"]["action_agreement"], "original_pool_ceiling": {"item_rows": pool, "denominator": len(pool), "recall_20_provenance": "Saved selected B3 has no reranking and preserves original candidate ordering; its Recall@20 uses the run's full indexed relevance universe. Same candidate membership is validated for R1.", "limitation": "Reranking cannot retrieve missing chunks or source spans outside the original candidate pool."},
            "same_request_reranking": rerank_analysis(groups["R1"], items, seed, samples), "latency_pairs": latency_analysis(groups["B3"], groups["R1"], ids, seed, samples), "recorded_latency_policy": manifest.get("latency_policy"), "actions": action,
            "initial_C2_to_current_B3_bundled_changes": changes, "answer_accuracy": None, "semantic_citation_support": None, "human_review_status": "HUMAN_REVIEW_PENDING",
            "limits": ["AI-authored diagnostic evidence/actions remain unverified; all semantic quality metrics are unknown.", "Lexical pass measures saved action/fact-word overlap/guard outcomes; paraphrases can fail and false statements can pass.", "Paired percentile intervals use exact item IDs, without multiple-comparison or annotation-uncertainty adjustments.", "All-request latency includes early refusal/clarification. Retrieval-executed latency and stage timings expose their own denominators.", "Timings are observed under cache state, two-query contention and provider variability; they do not establish portable latency or isolate all execution-order effects.", "Current B3 means hybrid without reranking; initial historical B3 meant hybrid with reranking. The initial run is never relabeled or overwritten."]}


def markdown(report):
    lines = ["# Current candidate diagnostic analysis", "", f"Current run: `{report['current_run']}`; initial run: `{report['initial_run']}`.", "", "Selected B3 is hybrid without reranking; R1 adds reranking to the same current configuration. Human semantic accuracy and citation support remain unknown.", "", "| B3 → R1 metric | Paired n | Before | After | Difference | Paired 95% interval |", "| --- | ---: | ---: | ---: | ---: | --- |"]
    for name, data in report["B3_to_R1_paired_metrics"].items():
        comparison = data["comparison"]
        if comparison:
            low, high = comparison["ci95"]
            lines.append(f"| {name} | {comparison['paired_denominator']} | {comparison['before_mean']:.3f} | {comparison['after_mean']:.3f} | {comparison['difference']:+.3f} | [{low:+.3f}, {high:+.3f}] |")
    lines += ["", "## Original candidate ceiling", "", "```json", json.dumps(report["original_pool_ceiling"], indent=2), "```", "", "## Observed paired latency", "", "| Metric (ms) | Paired n | Before mean | After mean | Difference | Paired 95% interval |", "| --- | ---: | ---: | ---: | ---: | --- |"]
    for metric, data in report["latency_pairs"].items():
        comparison = data["comparison"]
        if comparison:
            low, high = comparison["ci95"]
            lines.append(f"| {metric} | {comparison['paired_denominator']} | {comparison['before_mean']:.1f} | {comparison['after_mean']:.1f} | {comparison['difference']:+.1f} | [{low:+.1f}, {high:+.1f}] |")
    lines += ["", "## Bundled correction stage", "", report["initial_C2_to_current_B3_bundled_changes"]["scope"], "", "```json", json.dumps(report["initial_C2_to_current_B3_bundled_changes"]["metrics"], indent=2), "```", "", "Detailed actions, exact exclusions, rerank evidence changes, timings, hashes and control checks are in candidate-analysis.json.", "", "## Limits", ""]
    lines.extend(f"- {limit}" for limit in report["limits"])
    return "\n".join(lines) + "\n"


def self_test():
    old = {"X": {"expected_action": "answer", "result": {"response": {"action": "refuse"}}, "grade": {"diagnostic_pass": False}}}
    new = {"X": {"expected_action": "answer", "result": {"response": {"action": "answer"}}, "grade": {"diagnostic_pass": False}}}
    paired = bundled_changes(old, new, ["X"], 633, 100)
    assert paired["metrics"]["action_agreement"]["comparison"]["difference"] == 1
    assert paired["metrics"]["provisional_lexical_pass"]["comparison"]["difference"] == 0
    assert paired["metrics"]["action_agreement"]["improved_ids"] == ["X"]
    assert latency_value({"result": {"retrieval": {"timings": {}}}}, "rerank_ms") is None
    print("Pure synthetic candidate analysis checks passed; no provider calls or file writes.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_folder", nargs="?")
    parser.add_argument("--initial", type=Path)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/evaluation/diagnostic.jsonl")
    parser.add_argument("--seed", type=int, default=633)
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    current = args.run_folder or json.loads((ROOT / "artifacts/latest-diagnostic.json").read_text())["run"]
    initial = args.initial or json.loads((ROOT / "artifacts/initial-diagnostic.json").read_text())["run"]
    if args.samples < 1:
        parser.error("Positive bootstrap sample count required")
    report = analyze(current, initial, args.dataset, args.seed, args.samples)
    identity = {"inputs": report["input_sha256"], "seed": args.seed, "samples": args.samples, "script": file_hash(__file__), "shared_analysis_helpers": file_hash(Path(__file__).with_name("analyze_diagnostics.py"))}
    destination = Path(current) / ("candidate-analysis-" + digest(identity)[:12])
    destination.mkdir(exist_ok=True)
    for filename, text in (("candidate-analysis.json", json.dumps(report, indent=2) + "\n"), ("candidate-analysis.md", markdown(report))):
        path = destination / filename
        if path.exists():
            if path.read_text() != text:
                raise ValueError("Existing derived analysis differs; cannot overwrite")
        else:
            with path.open("x") as stream:
                stream.write(text)
    print(json.dumps({"analysis_folder": str(destination.resolve()), "items_per_variant": report["items_per_variant"], "human_review_status": report["human_review_status"]}, indent=2))


if __name__ == "__main__":
    main()
