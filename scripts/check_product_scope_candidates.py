"""Offline source/schema/scope checks, not retrieval or semantic performance tests.

Only imports the request schema and pure preflight helpers. Never invokes answer,
embedding, generation, HTTP clients, the legacy evaluator or a sealed test.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

from parkguide.chat import _positive_parks, preflight_response, scoped_preflight
from parkguide.web import ChatRequest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/evaluation/product-scope-v1"
REPORT = ROOT / "artifacts/evaluation-functionality/offline-validation.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    manifest = json.loads((DATA / "manifest.json").read_text())
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    for path, expected in manifest["input_hashes"].items():
        check(sha(ROOT / path) == expected, f"Original input changed: {path}")
    check(sha(ROOT / "scripts/prepare_product_scope_candidates.py") == manifest["builder_sha256"], "Revision builder changed")
    for path, expected in manifest["contract_file_hashes"].items():
        check(sha(ROOT / path) == expected, f"Product contract changed: {path}")
    check(sha(ROOT / "data/parkguide.sqlite") == manifest["database_sha256"], "Frozen database changed")
    for name, expected in manifest["output_hashes"].items():
        check(sha(DATA / name) == expected, f"Revision manifest stale: {name}")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    check(commit == manifest["code_commit"], "Current code commit differs from the revision manifest")
    conn = sqlite3.connect((ROOT / "data/parkguide.sqlite").as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    documents = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM documents")}
    gold = rows(DATA / "gold-candidates.jsonl")
    controls = rows(DATA / "scope-controls.jsonl")
    diagnostics = rows(DATA / "diagnostic-candidates.jsonl")
    dialogues = rows(DATA / "dialogue-candidates.jsonl")
    turns = [t for d in dialogues for t in d["turns"]]
    check(len(gold) == 40 and len(controls) == 4 and len(diagnostics) == 12 and len(dialogues) == 6 and len(turns) == 18, "Unexpected suite sizes")
    for d in dialogues:
        check(len(d["turns"]) == 3, f"{d['dialogue_id']}: expected three planned turns")
        check(all(t["selected_park"] == d["selected_park"] for t in d["turns"]), f"{d['dialogue_id']}: park changes inside chat")
        check(all("history" not in t and "actual" in t["history_from"] for t in d["turns"]), f"{d['dialogue_id']}: canned history supplied")
    check(len({r["item_id"] for r in gold + controls + diagnostics + turns}) == 74, "Duplicate IDs")
    observations = []
    evidence_count = 0
    for row in gold + controls + diagnostics + turns:
        item_id, park = row["item_id"], row["selected_park"]
        check(row["verification_status"] == "human_review_pending" and row["human_verifier"] is None and row["verified_at"] is None and row["benchmark_eligible"] is False, f"{item_id}: false human verification/benchmark eligibility")
        try:
            # For dialogue follow-ups this checks only the field shape. No actual
            # history exists yet, so it cannot establish conversation correctness.
            ChatRequest.model_validate({"selected_park": park, "question": row["question"], "history": row.get("history", [])})
        except ValueError:
            errors.append(f"{item_id}: invalid API request shape")
        foreign = [p for p in _positive_parks(row["question"]) if p != park]
        check(not foreign or row["category"] == "scope_boundary", f"{item_id}: foreign park in a knowledge question")
        check(bool(row["behavior_requirements"]), f"{item_id}: missing behavior rubric")
        for unit in row["evidence"]:
            evidence_count += 1
            source = documents.get(unit["doc_id"])
            check(source is not None, f"{item_id}: unresolved source")
            if source is None:
                continue
            parsed = json.loads(source["normalized_blocks_json"])
            text = parsed["normalized_text"]
            check(source["source_url"] == unit["source_url"] and unit["source_url"].startswith(f"https://www.nps.gov/{park}/planyourvisit/"), f"{item_id}: source identity/scope mismatch")
            check(hashlib.sha256(text.encode()).hexdigest() == unit["content_hash"] == source["content_hash"], f"{item_id}: source hash mismatch")
            check(text[unit["start"]:unit["end"]] == unit["quote"], f"{item_id}: quote/span mismatch")
            check(len(unit["quote"].split()) <= 25, f"{item_id}: quote longer than 25 words")
            check(any(b["start"] <= unit["start"] < b["end"] and b["heading_path"] == unit["heading_path"] for b in parsed["blocks"]), f"{item_id}: heading mismatch")
        if row in turns:
            continue  # Follow-up action requires actual preceding responses.
        result = scoped_preflight(row["question"], park)
        result = result or preflight_response(row["question"], [], {"parks": [park]})
        if result:
            check(result["action"] == row["expected_action"], f"{item_id}: deterministic preflight conflicts with proposed action")
        observations.append({"item_id": item_id, "expected_action": row["expected_action"], "preflight_action": result["action"] if result else None,
                             "preflight_reason": result.get("preflight_reason") if result else None,
                             "remaining_check": "real retrieval/generation and semantic grading needed" if not result else "controlled behavior observed; quality rubric still requires review"})
    # The original four comparative prompts cannot be answered for any selector.
    original_scope_checks = []
    for row in rows(ROOT / "data/evaluation/gold-drafts.jsonl")[21:25]:
        for park in ["yose", "yell", "grca"]:
            result = scoped_preflight(row["question"], park)
            check(result and result["action"] == "refuse" and result["preflight_reason"] == "selected_park_mismatch", f"{row['item_id']}/{park}: original cross-park control did not refuse")
            original_scope_checks.append({"item_id": row["item_id"], "selected_park": park, "action": result["action"] if result else None, "reason": result.get("preflight_reason") if result else None})
    check(sha(ROOT / "data/parkguide.sqlite") == manifest["database_sha256"], "Database changed during validation")
    conn.close()
    report = {"kind": "offline_contract_and_source_integrity_only", "code_commit": commit,
              "dataset_manifest_sha256": sha(DATA / "manifest.json"), "errors": errors,
              "counts": {"candidate_rows": 74, "request_field_shapes": 74, "source_evidence_units": evidence_count, "original_cross_park_preflight_checks": len(original_scope_checks)},
              "knowledge_categories": dict(Counter(r["category"] for r in gold)),
              "knowledge_selected_parks": dict(Counter(r["selected_park"] for r in gold)),
              "preflight_observations": observations, "original_cross_park_preflight_checks": original_scope_checks,
              "limitations": ["No actual chat, retrieval, generation, citation-support grading, hosted behavior or UI transitions were measured.", "Dialogue API checks used empty history for shape only; actual preceding assistant responses must be carried by a future product runner.", "Human semantic verification and a reviewed grouped dev/test split remain pending.", "Original corpus-QA labeling outputs remain unchanged; none is newly certified as product gold."],
              "paid_calls": 0, "application_requests": 0, "benchmark_eligible": False,
              "source_integrity_and_static_contract_pass": not errors}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"report": str(REPORT.relative_to(ROOT)), "counts": report["counts"], "errors": errors, "paid_calls": 0}))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
