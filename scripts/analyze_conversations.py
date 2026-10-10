#!/usr/bin/env python3
"""Cluster uncertainty for saved provisional AI conversation review; no API calls."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def cluster_interval(numerators, denominators, *, seed=633, samples=10000):
    numerators, denominators = np.asarray(numerators, dtype=int), np.asarray(denominators, dtype=int)
    if numerators.shape != denominators.shape or numerators.ndim != 1 or not len(numerators) or np.any(numerators < 0) or np.any(denominators < numerators) or samples < 1:
        raise ValueError("Need valid numerator/denominator pairs for nonempty clusters")
    if denominators.sum() == 0:
        return {"numerator": 0, "denominator": 0, "fraction": None, "ci95": None, "cluster_count": len(numerators), "valid_draws": 0, "zero_denominator_draws": samples, "seed": seed, "samples": samples}
    indices = np.random.default_rng(seed).integers(0, len(numerators), (samples, len(numerators)))
    tops, bottoms = numerators[indices].sum(axis=1), denominators[indices].sum(axis=1)
    valid = bottoms > 0
    draws = tops[valid] / bottoms[valid]
    bounds = np.percentile(draws, [2.5, 97.5])
    return {"numerator": int(numerators.sum()), "denominator": int(denominators.sum()), "fraction": float(numerators.sum() / denominators.sum()), "ci95": [float(bounds[0]), float(bounds[1])], "cluster_count": len(numerators), "valid_draws": int(valid.sum()), "zero_denominator_draws": int((~valid).sum()), "degenerate": bool(np.all(draws == draws[0])), "seed": seed, "samples": samples}


def analyze(review_path, folder, *, seed=633, samples=10000, expected_review_sha=None):
    review_path, folder = Path(review_path).resolve(), Path(folder).resolve()
    review_hash = sha256(review_path)
    if expected_review_sha and review_hash != expected_review_sha:
        raise ValueError("Review hash differs from the selected snapshot")
    review = [row for row in read_jsonl(review_path) if row.get("kind") == "dialogue"]
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest.get("kind") != "non_gold_dialogue_diagnostic":
        raise ValueError("Only non-gold dialogue artifacts are permitted")
    actual_path = folder / "results.jsonl"
    actual = read_jsonl(actual_path)
    actual_hash = sha256(actual_path)
    saved = {(row["dialogue_id"], row["turn"]): row for row in actual}
    if len(saved) != len(actual) or len(review) != len(saved):
        raise ValueError("Review must cover all unique attempted dialogue turns")
    groups = defaultdict(list)
    seen = set()
    for row in review:
        key = (row["dialogue_id"], row["turn"])
        if key in seen or key not in saved:
            raise ValueError("Missing or duplicate reviewed dialogue/turn IDs")
        seen.add(key)
        if row.get("formal_benchmark_eligible") is not False or row.get("human_review_pending") is not True or row.get("human_verifier") is not None or row.get("reviewer") != "AI_subagent":
            raise ValueError("This analysis requires explicitly provisional AI diagnostic review")
        if Path(row["input_artifact"]).resolve() != actual_path or row["input_artifact_sha256"] != actual_hash:
            raise ValueError("Review provenance differs from the actual dialogue artifact")
        if row.get("semantic_correct") not in (True, False, "uncertain"):
            raise ValueError("Unknown semantic-review label; do not silently exclude it")
        original = saved[key]
        if "result" in original:
            result = original["result"]
            if result["response"] != row["delivered_response"] or result["question"] != row["question"]:
                raise ValueError("Reviewed response differs from the actual delivered turn")
        counts = row["claim_counts"]
        if any(type(counts[name]) is not int or counts[name] < 0 for name in ("supported", "uncertain", "unsupported", "total")) or counts["supported"] + counts["uncertain"] + counts["unsupported"] != counts["total"]:
            raise ValueError("Claim-support counts are inconsistent")
        groups[row["dialogue_id"]].append(row)
    if len(groups) != 6 or any(sorted(row["turn"] for row in group) != [1, 2, 3] for group in groups.values()):
        raise ValueError("Expected six complete three-turn dialogue clusters")
    per_dialogue, histories_valid = [], True
    for identifier, group in sorted(groups.items()):
        group = sorted(group, key=lambda row: row["turn"])
        history = []
        for row in group:
            original = saved[(identifier, row["turn"])]
            if "result" not in original:
                continue
            result = original["result"]
            histories_valid = histories_valid and result["history"] == history
            history.extend([{"role": "user", "content": result["question"]}, {"role": "assistant", "content": result["rendered"]}])
        per_dialogue.append({"dialogue_id": identifier, "item_ids": [row["item_id"] for row in group], "turns": len(group), "clearly_correct": sum(row["semantic_correct"] is True for row in group), "incorrect": sum(row["semantic_correct"] is False for row in group), "uncertain": sum(row["semantic_correct"] == "uncertain" for row in group), "supported_claims": sum(row["claim_counts"]["supported"] for row in group), "unsupported_claims": sum(row["claim_counts"]["unsupported"] for row in group), "uncertain_claims": sum(row["claim_counts"]["uncertain"] for row in group), "total_claims": sum(row["claim_counts"]["total"] for row in group)})
    if not histories_valid:
        raise ValueError("Actual saved history is not exclusively preceding delivered turns")
    correct = cluster_interval([row["clearly_correct"] for row in per_dialogue], [row["turns"] for row in per_dialogue], seed=seed, samples=samples)
    support = cluster_interval([row["supported_claims"] for row in per_dialogue], [row["total_claims"] for row in per_dialogue], seed=seed, samples=samples)
    return {"kind": "PROVISIONAL_AI_NON_GOLD_CONVERSATION_CLUSTER_ANALYSIS", "review_file": str(review_path), "review_sha256": review_hash, "dialogue_folder": str(folder), "dialogue_results_sha256": actual_hash, "dialogue_manifest_sha256": sha256(folder / "manifest.json"), "config_hash": manifest.get("config_hash"), "code_hash": manifest.get("code_hash"), "per_dialogue": per_dialogue,
            "clearly_correct_fraction_all_attempted_turns": correct, "observed_turn_labels": {"clearly_correct": correct["numerator"], "incorrect": sum(row["incorrect"] for row in per_dialogue), "uncertain": sum(row["uncertain"] for row in per_dialogue), "total": correct["denominator"], "uncertain_item_ids": [row["item_id"] for row in review if row["semantic_correct"] == "uncertain"]},
            "supported_claim_fraction_all_delivered_claims": support, "observed_claim_labels": {"supported": support["numerator"], "unsupported": sum(row["unsupported_claims"] for row in per_dialogue), "uncertain": sum(row["uncertain_claims"] for row in per_dialogue), "total": support["denominator"]}, "pipeline_errors": sum("error" in row for row in actual), "actual_history_snapshot_verified": histories_valid, "human_answer_accuracy": None, "human_citation_support": None,
            "method": "10,000 percentile bootstrap draws with seed 633 by default. Each draw samples six whole dialogues with replacement, preserves every turn/claim in each chosen cluster, and computes a ratio of total numerators to total denominators.",
            "limits": ["All labels are source-based AI proposals on non-gold development diagnostics; human semantic verification remains pending.", "Uncertain turns and claims remain in their total denominators and are not counted clearly correct/supported or relabeled incorrect/unsupported.", "The interval describes sampling variation of the fixed AI labels, not human accuracy, judge correctness, annotation uncertainty or held-out performance.", "Six authored dialogues are a small, non-random development set; clustering accounts for within-dialogue dependence only.", "There is no before/after causal comparison or claimed final acceptance in this analysis."]}


def self_test():
    measured = cluster_interval([3, 0], [3, 1], seed=633, samples=1000)
    assert measured["fraction"] == .75 and measured["ci95"] == [0, 1]
    assert cluster_interval([3, 3], [3, 3], samples=1000)["degenerate"]
    assert cluster_interval([0, 0], [0, 0], samples=1000)["fraction"] is None
    print("Synthetic whole-cluster ratio checks passed; no API calls or file writes.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=ROOT / "artifacts/reviews/latest-semantic-review.jsonl")
    parser.add_argument("--dialogue-folder", type=Path)
    parser.add_argument("--expected-review-sha")
    parser.add_argument("--seed", type=int, default=633)
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    folder = args.dialogue_folder or Path(json.loads((ROOT / "artifacts/latest-dialogues.json").read_text())["folder"])
    report = analyze(args.review, folder, seed=args.seed, samples=args.samples, expected_review_sha=args.expected_review_sha)
    identity = {"review": report["review_sha256"], "results": report["dialogue_results_sha256"], "manifest": report["dialogue_manifest_sha256"], "seed": args.seed, "samples": args.samples, "script": sha256(__file__)}
    suffix = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]
    destination = folder / ("conversation-analysis-" + suffix)
    destination.mkdir(exist_ok=True)
    path = destination / "conversation-analysis.json"
    text = json.dumps(report, indent=2) + "\n"
    if path.exists():
        if path.read_text() != text:
            raise ValueError("Existing derived analysis differs; cannot overwrite")
    else:
        with path.open("x") as stream:
            stream.write(text)
    print(json.dumps({"analysis_file": str(path.resolve()), "clearly_correct": report["clearly_correct_fraction_all_attempted_turns"], "supported_claims": report["supported_claim_fraction_all_delivered_claims"], "human_review_status": "PENDING"}, indent=2))


if __name__ == "__main__":
    main()
