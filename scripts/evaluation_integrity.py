"""Read-only validation of the frozen, AI-provisional gold-matrix study."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3

from gold_matrix import CONFIGS, DATA, ROOT, RUN, readlines, sha

ACTIONS = ("answer", "refuse", "clarify")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read evaluation JSON: {path}") from error


def unique_rows(rows, label, *, key="item_id", expected_ids=None, count=None):
    require(isinstance(rows, list), f"{label} must be a list")
    require(all(isinstance(row, dict) and isinstance(row.get(key), str) and row[key] for row in rows),
            f"{label} need nonempty {key} values")
    identifiers = [row[key] for row in rows]
    require(len(identifiers) == len(set(identifiers)), f"Duplicate {key} in {label}")
    if count is not None:
        require(len(rows) == count, f"{label} must contain {count} rows")
    if expected_ids is not None:
        require(set(identifiers) == set(expected_ids), f"{label} IDs do not match the frozen cases")
    return {row[key]: row for row in rows}


def check_hash(path, expected):
    require(isinstance(expected, str) and len(expected) == 64, f"Missing frozen SHA-256 for {path}")
    try:
        actual = sha(path)
    except OSError as error:
        raise ValueError(f"Missing frozen evaluation input: {path}") from error
    require(actual == expected, f"Frozen SHA-256 mismatch: {path}")
    return actual


def validate_response_rows(rows, *, expected_ids=None, count=40):
    """Check trace shape, while retaining real errors and invalid citations as scores."""
    bots = unique_rows(rows, "responses", expected_ids=expected_ids, count=count)
    for item_id, bot in bots.items():
        has_result, has_error = "result" in bot, bool(bot.get("error"))
        require(has_result != has_error, f"{item_id}: expected result XOR nonempty error")
        if has_error:
            require(isinstance(bot["error"], dict), f"{item_id}: error must be an object")
            continue
        result = bot["result"]
        require(isinstance(result, dict), f"{item_id}: result must be an object")
        elapsed = result.get("elapsed_ms")
        require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
                f"{item_id}: elapsed_ms must be finite and nonnegative")
        response = result.get("response")
        require(isinstance(response, dict) and response.get("action") in ACTIONS,
                f"{item_id}: invalid response action")
        require(isinstance(response.get("answer"), str), f"{item_id}: answer must be text")
        claims = response.get("claims")
        require(isinstance(claims, list), f"{item_id}: claims must be a list")
        for claim in claims:
            require(isinstance(claim, dict) and isinstance(claim.get("text"), str),
                    f"{item_id}: invalid claim text")
            evidence = claim.get("evidence_ids")
            require(isinstance(evidence, list) and all(isinstance(value, str) for value in evidence),
                    f"{item_id}: evidence_ids must be a list of strings")
        retrieval = result.get("retrieval")
        require(isinstance(retrieval, dict), f"{item_id}: retrieval must be an object")
        for name, chunks in [("contexts", result.get("contexts")),
                             ("candidates", retrieval.get("candidates")),
                             ("reranked", retrieval.get("reranked", []))]:
            unique_rows(chunks, f"{item_id} {name}", key="chunk_id")
            for chunk in chunks:
                require(all(isinstance(chunk.get(key), str) for key in
                            ("doc_id", "content_hash", "source_url", "text")),
                        f"{item_id}: incomplete {name} chunk")
        require(isinstance(result.get("guard_errors", []), list), f"{item_id}: guard_errors must be a list")
    return bots


def validate_frozen_inputs(*, include_semantic=True, database=None, root=None, data=None, run=None):
    """Validate existing seals; never replace them with freshly computed hashes.

    No original course questions, credentials, provider code, or network is read.
    Path overrides support isolated contract fixtures, not a new evaluation run.
    """
    root, data, run = Path(root or ROOT), Path(data or DATA), Path(run or RUN)
    manifest = read_json(data / "manifest.json")
    consensus = read_json(data / "consensus-manifest.json")
    freeze = read_json(run / "label-freeze.json")
    botmeta = read_json(run / "chatbot/metadata.json")
    result_manifest = run / "result-manifest.json"
    require(result_manifest.is_file(),
            "Missing provenance seal: restore the tracked result-manifest.json from a trusted revision before replay")
    sealed = read_json(result_manifest).get("artifacts_sha256", {})
    # Only immutable inputs participate: changed scorer/report source and
    # regenerated aggregates are expected during an offline replay. A missing
    # seal must never let --write bless changed historical provenance.
    provenance_paths = [(data, "data/evaluation/gold-matrix-v1", name)
                        for name in ("manifest.json", "consensus-manifest.json")]
    provenance_paths += [(run, "artifacts/gold-matrix-v1", "chatbot/metadata.json")]
    provenance_paths += [(run, "artifacts/gold-matrix-v1", f"reviewers/{name}/provenance.json") for name in CONFIGS]
    if include_semantic:
        provenance_paths += [(run, "artifacts/gold-matrix-v1", name) for name in
                             ("semantic-provenance.json", "semantic-assessment.raw.json")]
    for base, prefix, name in provenance_paths:
        check_hash(base / name, sealed.get(f"{prefix}/{name}"))
    database = Path(database) if database is not None else root / "data/parkguide.sqlite"
    identities = {
        "annotation_input_sha256": check_hash(data / "annotation-input.json", manifest.get("input_sha256")),
        "dataset_sha256": check_hash(data / "gold-consensus.jsonl", consensus.get("dataset_sha256")),
        "responses_sha256": check_hash(run / "chatbot/responses.jsonl", botmeta.get("responses_sha256")),
        "database_sha256": check_hash(database, manifest.get("database_sha256")),
        "label_freeze_sha256": check_hash(run / "label-freeze.json", consensus.get("label_freeze_sha256")),
        "adjudication_sha256": check_hash(run / "adjudication.frozen.json", consensus.get("adjudication_sha256")),
        "build_id": botmeta.get("build_id"),
    }
    for label, expected in [("label freeze", freeze.get("input_sha256")), ("chatbot run", botmeta.get("input_sha256"))]:
        require(expected == identities["annotation_input_sha256"], f"{label}: annotation input hash mismatch")
    require(isinstance(identities["build_id"], str) and identities["build_id"], "Missing frozen index build ID")
    require(set(freeze.get("label_hashes", {})) == set(CONFIGS), "The frozen labeler set has changed")
    cases = unique_rows(read_json(data / "annotation-input.json").get("cases"), "annotation cases", count=40)
    refs = unique_rows(readlines(data / "gold-consensus.jsonl"), "references", expected_ids=cases, count=40)
    bots = validate_response_rows(readlines(run / "chatbot/responses.jsonl"), expected_ids=cases)
    for name, digest in freeze["label_hashes"].items():
        directory = run / "reviewers" / name
        check_hash(directory / "labels.json", digest)
        check_hash(directory / "labels.raw.json", digest)
        labels = unique_rows(read_json(directory / "labels.json").get("labels"), name, expected_ids=cases, count=40)
        require(all(label.get("action") in ACTIONS for label in labels.values()), f"{name}: invalid action label")
    for item_id, case in cases.items():
        require(bots[item_id].get("request") == case, f"{item_id}: saved request differs from frozen case")
        require(all(refs[item_id].get(key) == case.get(key) for key in ("question", "selected_park", "history")),
                f"{item_id}: reference setup differs from frozen case")
        require(refs[item_id].get("action") in ACTIONS, f"{item_id}: invalid reference action")
        result_build = bots[item_id].get("result", {}).get("retrieval", {}).get("build_id")
        require(result_build is None or result_build == identities["build_id"], f"{item_id}: retrieval build mismatch")
    if include_semantic:
        provenance = read_json(run / "semantic-provenance.json")
        identities["semantic_input_sha256"] = check_hash(run / "semantic-input.json", provenance.get("input", {}).get("sha256"))
        packet = read_json(run / "semantic-input.json")
        for key in ("reference_sha256", "responses_sha256"):
            expected = identities["dataset_sha256" if key == "reference_sha256" else key]
            require(packet.get(key) == expected and provenance["input"].get(key) == expected,
                    f"Semantic input: {key} mismatch")
        unique_rows(packet.get("cases"), "semantic cases", expected_ids=cases, count=40)
        raw_assessment = run / "semantic-assessment.raw.json"
        require(raw_assessment.is_file(), "Missing frozen raw semantic assessment")
        identities["assessment_sha256"] = check_hash(run / "semantic-assessment.json", sha(raw_assessment))
    return identities


def load_frozen_chunks(database, build_id):
    """Load the historical qrel universe using an explicitly read-only connection."""
    with sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT manifest_json FROM index_builds WHERE build_id=?", (build_id,)).fetchone()
        require(row is not None, "Frozen index build is missing from the database")
        manifest = json.loads(row["manifest_json"])
        rows = connection.execute("SELECT * FROM chunks WHERE build_id=? ORDER BY chunk_id", (build_id,)).fetchall()
    require(rows, "Frozen index build has no chunks")
    chunks = []
    for row in rows:
        chunk = dict(row)
        chunk.update(manifest["document_snapshot"][chunk["doc_id"]])
        chunk["source_span"] = json.loads(chunk["source_span_json"])
        chunks.append(chunk)
    return chunks
