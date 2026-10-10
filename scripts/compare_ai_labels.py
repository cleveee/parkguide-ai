"""Validate independent AI labels and build a review sheet without adjudicating them."""
from __future__ import annotations

import hashlib
import itertools
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/evaluation/ai-labeling/sample-v1"
OUTPUT = ROOT / "artifacts/ai-labeling/sample-v1"
REVIEWERS = ["codex-a", "codex-b", "codex-c", "claude-code"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def schema_errors(value, schema, path="root"):
    errors = []
    kind = schema.get("type")
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str)}
    if kind and not valid.get(kind, False):
        return [f"{path}: expected {kind}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: invalid enum")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing {key}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            errors.extend(f"{path}: unexpected {key}" for key in set(value) - set(props))
        for key in set(value) & set(props):
            errors.extend(schema_errors(value[key], props[key], f"{path}.{key}"))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            errors.append(f"{path}: wrong item count")
        for n, item in enumerate(value):
            errors.extend(schema_errors(item, schema.get("items", {}), f"{path}[{n}]"))
    return errors


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def main():
    frozen = json.loads((INPUT / "manifest.json").read_text())
    projection = json.loads((INPUT / "annotation-input-manifest.json").read_text())
    packet = json.loads((INPUT / "annotation-input.json").read_text())
    schema = json.loads((INPUT / "labels.schema.json").read_text())
    output_manifest = OUTPUT / "label-manifest.json"
    if output_manifest.exists():
        saved_outputs = json.loads(output_manifest.read_text())
        for reviewer, files in saved_outputs["outputs"].items():
            for name, expected in files.items():
                assert sha(OUTPUT / reviewer / name) == expected, f"Original annotation changed: {reviewer}/{name}"
        assert sha(OUTPUT / "claude-code/cli-response.json") == saved_outputs["claude_raw_response_sha256"]
    cases = packet["cases"]
    assert sha(INPUT / "annotation-input.json") == projection["annotation_input_sha256"]
    for name, expected in frozen["files"].items():
        assert sha(INPUT / name) == expected, f"Frozen file changed: {name}"
    assert sha(ROOT / "data/parkguide.sqlite") == frozen["database_sha256"]
    for name, expected in frozen["protected_files"].items():
        assert sha(ROOT / name) == expected, f"Existing gold file changed: {name}"
    db = sqlite3.connect((ROOT / "data/parkguide.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    sources = {s["source_id"]: s for s in packet["sources"]}
    for source in sources.values():
        row = db.execute("SELECT source_url,content_hash,normalized_blocks_json FROM documents WHERE doc_id=?", [source["doc_id"]]).fetchone()
        assert row and row[0] == source["source_url"] and row[1] == source["content_hash"]
        assert json.loads(row[2])["normalized_text"] == source["normalized_text"]
    all_labels, audits = {}, {}
    for reviewer in REVIEWERS:
        path = OUTPUT / reviewer / "labels.json"
        labels = json.loads(path.read_text())
        provenance = json.loads((path.parent / "provenance.json").read_text())
        input_hash = provenance.get("input_sha256", provenance.get("input_hash"))
        assert input_hash == projection["annotation_input_sha256"]
        errors = schema_errors(labels, schema)
        assert not errors, f"{reviewer}: {errors}"
        assert [r["item_id"] for r in labels["labels"]] == [c["item_id"] for c in cases]
        all_labels[reviewer] = {r["item_id"]: r for r in labels["labels"]}
        evidence_errors, spans, uncovered = [], [], {}
        for label in labels["labels"]:
            item_id = label["item_id"]
            facts = [f["fact_id"] for f in label["required_facts"]]
            assert len(facts) == len(set(facts)), f"{reviewer}/{item_id}: duplicate fact ID"
            covered = set()
            for n, evidence in enumerate(label["evidence"]):
                source = sources.get(evidence["source_id"])
                quote = evidence["quote"]
                problems = []
                if not source:
                    problems.append("unknown source_id")
                if not quote.strip():
                    problems.append("empty quote")
                if len(quote.split()) > 25:
                    problems.append("quote exceeds 25 words")
                if not set(evidence["fact_ids"]) <= set(facts):
                    problems.append("unknown fact_id")
                offsets = []
                if source and quote:
                    start = 0
                    while (pos := source["normalized_text"].find(quote, start)) >= 0:
                        offsets.append({"start": pos, "end": pos + len(quote)})
                        start = pos + len(quote)
                    if not offsets:
                        problems.append("quote is not verbatim saved text")
                if problems:
                    evidence_errors.append({"item_id": item_id, "evidence_index": n, "problems": problems})
                else:
                    covered.update(evidence["fact_ids"])
                spans.append({"item_id": item_id, "evidence_index": n, "source_id": evidence["source_id"], "doc_id": source["doc_id"] if source else None, "source_url": source["source_url"] if source else None, "content_hash": source["content_hash"] if source else None, "quote": quote, "fact_ids": evidence["fact_ids"], "matching_character_spans": offsets, "multiple_occurrences": len(offsets) > 1, "mechanically_valid": not problems})
            if set(facts) - covered:
                uncovered[item_id] = sorted(set(facts) - covered)
        audits[reviewer] = {"input_sha256": input_hash, "labels_sha256": sha(path), "case_count": len(labels["labels"]), "quote_count": len(spans), "evidence_errors": evidence_errors, "facts_without_mechanically_valid_quote": uncovered, "note": "Exact source identity/quote checks do not establish semantic support. Refusal and clarification requirements may be unsupported by design; inspect uncovered facts rather than assume a grounding failure.", "spans": spans}
        dump(path.parent / "source-validation.json", audits[reviewer])
    comparisons = []
    candidates = []
    for case in cases:
        labels = {r: all_labels[r][case["item_id"]] for r in REVIEWERS}
        actions = Counter(label["action"] for label in labels.values())
        answerabilities = Counter(label["answerability"] for label in labels.values())
        comparisons.append({"item_id": case["item_id"], "actions": dict(actions), "answerabilities": dict(answerabilities), "action_unanimous": len(actions) == 1, "answerability_unanimous": len(answerabilities) == 1, "labels": {r: {k: v[k] for k in ["action", "answerability", "confidence"]} for r, v in labels.items()}, "semantic_answer_agreement": "not scored"})
        candidates.append({**case, "verification_status": "human_review_pending", "human_verifier": None, "verified_at": None, "benchmark_eligible": False, "annotation_type": "independent AI reference proposals", "references": labels, "adjudicated_reference": None, "comparison": comparisons[-1]})
    pairs = []
    for a, b in itertools.combinations(REVIEWERS, 2):
        pairs.append({"reviewers": [a, b], "n": len(cases), "action_agreement": sum(all_labels[a][c["item_id"]]["action"] == all_labels[b][c["item_id"]]["action"] for c in cases), "answerability_agreement": sum(all_labels[a][c["item_id"]]["answerability"] == all_labels[b][c["item_id"]]["answerability"] for c in cases)})
    summary = {"created_at": datetime.now(timezone.utc).isoformat(), "dataset_id": packet["dataset_id"], "n_questions": len(cases), "n_reviewers": len(REVIEWERS), "n_annotations": len(cases) * len(REVIEWERS), "unanimous_action_count": sum(c["action_unanimous"] for c in comparisons), "unanimous_answerability_count": sum(c["answerability_unanimous"] for c in comparisons), "pairwise": pairs, "items": comparisons, "source_validation": {r: {k: v[k] for k in ["case_count", "quote_count", "evidence_errors", "facts_without_mechanically_valid_quote", "labels_sha256"]} for r, v in audits.items()}, "limitations": ["AI labels remain proposals; no human gold verification or adjudication", "Three Codex runs inherit one parent model and are not three different models", "Reviewer isolation is by task instructions and separate inputs; subagents retain ordinary filesystem access", "Input includes ten complete relevant documents plus metadata/search excerpts for the 155-document snapshot; reviewers did not semantically inspect every document", "Purposive 18-case development sample with prior topic exposure; not a held-out benchmark", "Agreement on categorical action or answerability does not prove answer or evidence correctness", "No automatic majority reference or chatbot performance score", "Claude CLI cost is reported separately from Azure application spend"]}
    dump(OUTPUT / "comparison.json", summary)
    (INPUT / "reference-candidates.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in candidates))
    cli = json.loads((OUTPUT / "claude-code/provenance.json").read_text())
    cli_model = ", ".join(cli.get("model_usage", {})) or "unreported"
    lines = ["# Independent AI reference labels: sample v1", "", f"{len(cases)} questions × four independent reviewers = {len(cases) * 4} annotations. **Human review pending; no final gold labels have been chosen.**", "", f"All reviewers received identical questions, saved source text and instructions. Three Codex subagents inherited the same model; Claude Code CLI used its configured default, reported as `{cli_model}` (${cli.get('total_cost_usd')} reported CLI usage; {cli.get('cli_turn_count')} internal CLI turns in one invocation). The original 40 gold drafts remain unchanged. This is a new development sample, not the sealed final benchmark.", "", f"Unanimous action labels: **{summary['unanimous_action_count']}/{len(cases)}**. Unanimous answerability labels: **{summary['unanimous_answerability_count']}/{len(cases)}**. These measure categorical agreement, not answer accuracy or agreement on every required fact.", "", "| Item | Codex A | Codex B | Codex C | Claude Code |", "| --- | --- | --- | --- | --- |"]
    for case in cases:
        values = [f"{all_labels[r][case['item_id']]['action']} / {all_labels[r][case['item_id']]['answerability']}" for r in REVIEWERS]
        lines.append("| " + " | ".join([case["item_id"], *values]) + " |")
    lines += ["", "## Pairwise categorical agreement", "", "| Reviewers | Same action | Same answerability |", "| --- | --- | --- |"]
    for pair in pairs:
        lines.append(f"| {' / '.join(pair['reviewers'])} | {pair['action_agreement']}/{pair['n']} | {pair['answerability_agreement']}/{pair['n']} |")
    lines += ["", "## Review each proposed answer", "", "Keep the four original outputs separate. Choose approve, revise or reject for each reference after checking source context and exceptions. Fill the real human verifier/date only after review. No majority vote is automatically accepted."]
    for case in cases:
        lines += ["", f"### {case['item_id']}: {case['question']}", "", "| Reviewer | Action / answerability | Proposed reference answer | Rationale |", "| --- | --- | --- | --- |"]
        for r in REVIEWERS:
            label = all_labels[r][case["item_id"]]
            lines.append(f"| {r} | {label['action']} / {label['answerability']} | {cell(label['expected_answer'])} | {cell(label['rationale'])} |")
        lines += ["", "Human decision: pending. Adjudicated answer: pending. Human verifier/date: blank.", "", "Required facts, contradictions, confidence and exact evidence are retained in each reviewer's labels.json and source-validation.json."]
    lines += ["", "## Scope and verification limits", ""] + [f"- {s}" for s in summary["limitations"]]
    queue_path = OUTPUT / "human-review-queue.json"
    if queue_path.exists():
        queue = json.loads(queue_path.read_text())
        lines += ["", "## Focused human review queue", "", "These are root AI inspection prompts, not corrected labels or human decisions. All four original outputs are preserved.", ""]
        lines += [f"- **{item['item_id']}**: {item['review_focus']}" for item in queue["items"]]
    (OUTPUT / "REVIEW.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"annotations": summary["n_annotations"], "unanimous_actions": summary["unanimous_action_count"], "unanimous_answerability": summary["unanimous_answerability_count"], "evidence_errors": {r: len(v["evidence_errors"]) for r, v in audits.items()}, "existing_gold_and_database_unchanged": True}))


if __name__ == "__main__":
    main()
