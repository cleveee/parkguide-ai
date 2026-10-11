"""Offline replay and integrity checks for the saved AI-provisional study."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import socket
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import assess_gold_matrix as assess
import derive_gold_matrix as derive
import evaluation_integrity as integrity


def read(path):
    return json.loads(path.read_text())


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Gold-matrix replay must not use the network")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def test_saved_replay_preserves_scores_and_writes_only_requested_output(tmp_path):
    tracked_inputs = list(derive.DATA.rglob("*")) + list(derive.RUN.rglob("*"))
    before = {p: integrity.sha(p) for p in tracked_inputs if p.is_file()}
    metrics = derive.score(tmp_path / "replay")
    semantic = assess.summarize(tmp_path / "replay")
    assert metrics["action_metrics"] == read(derive.RUN / "metrics.json")["action_metrics"]
    assert metrics["action_metrics"]["accuracy"] == 37 / 40
    assert semantic["full_rubric_pass"]["passed"] == 21
    assert semantic["facts"]["covered"] == 55 and semantic["fact_total"] == 75
    for k, hits, covered in [(5, 35, 63), (20, 43, 72)]:
        retrieval = metrics["retrieval_metrics"][f"at_{k}"]
        assert (retrieval["tp"], retrieval["known_relevant"]) == (hits, 44)
        assert retrieval["facts_covered"] == covered and retrieval["facts_total"] == 75
        assert retrieval["fact_evidence_coverage_items"] == 30
        assert retrieval["fact_evidence_coverage_micro"] == covered / 75
    assert metrics["operational"]["completed"] == 40
    assert metrics["operational"]["guard_error_item_ids"] == ["M036"]
    assert semantic["human_verified"] is False and metrics["formal_course_benchmark"] is False
    assert {p: integrity.sha(p) for p in before} == before
    assert {p.name for p in (tmp_path / "replay").iterdir()} == {
        "agreement.json", "metrics.json", "qrels.json", "per-item-metrics.jsonl", "semantic-summary.json",
    }


@pytest.mark.parametrize("relative_path", [
    "data/evaluation/gold-matrix-v1/gold-consensus.jsonl",
    "data/evaluation/gold-matrix-v1/annotation-input.json",
    "artifacts/gold-matrix-v1/chatbot/responses.jsonl",
    "data/parkguide.sqlite",
    "artifacts/gold-matrix-v1/semantic-input.json",
    "artifacts/gold-matrix-v1/semantic-assessment.json",
    "artifacts/gold-matrix-v1/chatbot/metadata.json",
    "artifacts/gold-matrix-v1/reviewers/codex-sol/provenance.json",
])
def test_changed_frozen_input_is_rejected_before_output(tmp_path, monkeypatch, relative_path):
    """One copied file is changed; other frozen files are read-only symlinks."""
    data = tmp_path / "data/evaluation/gold-matrix-v1"
    run = tmp_path / "artifacts/gold-matrix-v1"
    for source, target in [(derive.DATA, data), (derive.RUN, run)]:
        for path in source.rglob("*"):
            if path.is_file():
                destination = target / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(path)
    database = tmp_path / "data/parkguide.sqlite"
    database.symlink_to(ROOT / "data/parkguide.sqlite")
    changed = tmp_path / relative_path
    source = changed.resolve()
    changed.unlink()
    shutil.copyfile(source, changed)
    with changed.open("ab") as stream:
        stream.write(b"\n")
    for module in (derive, assess):
        monkeypatch.setattr(module, "ROOT", tmp_path)
        monkeypatch.setattr(module, "DATA", data)
        monkeypatch.setattr(module, "RUN", run)
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        assess.summarize(output)
    assert not output.exists()


def valid_response():
    chunk = {"chunk_id": "c", "doc_id": "d", "content_hash": "hash", "source_url": "url", "text": "source"}
    return {"item_id": "M001", "result": {"elapsed_ms": 10, "response": {
        "action": "answer", "answer": "Fact", "claims": [{"text": "Fact", "evidence_ids": ["c"]}],
    }, "contexts": [chunk], "retrieval": {"candidates": [chunk]}}}


@pytest.mark.parametrize("elapsed", [float("nan"), float("inf"), -1, True, "10"])
def test_invalid_latency_does_not_enter_percentiles(elapsed):
    row = valid_response()
    row["result"]["elapsed_ms"] = elapsed
    with pytest.raises(ValueError, match="finite and nonnegative"):
        integrity.validate_response_rows([row], count=1)


def test_duplicate_responses_rankings_and_result_error_are_rejected():
    row = valid_response()
    with pytest.raises(ValueError, match="Duplicate item_id"):
        integrity.validate_response_rows([row, row], count=2)
    row["result"]["retrieval"]["candidates"] *= 2
    with pytest.raises(ValueError, match="Duplicate chunk_id"):
        integrity.validate_response_rows([row], count=1)
    row = valid_response()
    row["error"] = {"type": "failed"}
    with pytest.raises(ValueError, match="XOR"):
        integrity.validate_response_rows([row], count=1)


def test_failed_call_and_invalid_citation_are_kept_as_failures():
    error = {"item_id": "M001", "error": {"type": "timeout"}}
    assert integrity.validate_response_rows([error], count=1)["M001"] == error
    metrics = derive.classify(["answer", "refuse", "clarify"], ["answer", "error", "clarify"])
    assert metrics["micro_f1"] == 2 / 3 and metrics["per_class"][1]["fn"] == 1
    row = valid_response()
    row["result"]["response"]["claims"][0]["evidence_ids"] = ["unknown"]
    assert integrity.validate_response_rows([row], count=1)["M001"] == row


def test_zero_qrel_cases_keep_their_combined_context_coverage():
    def row(item_id, relevant, covered, total):
        retrieval = {"tp": 0, "retrieved": 2, "relevant": relevant, "precision": 0.0,
                     "recall": 0.0 if relevant else None, "f1": 0.0 if relevant else None,
                     "fact_evidence_coverage": covered / total, "facts_covered": covered, "facts_total": total}
        return {"item_id": item_id, "known_relevant_chunks": relevant,
                "retrieval_at_5": retrieval, "retrieval_at_20": retrieval,
                "generation_context_fact_evidence_coverage": covered / total,
                "generation_context_facts_covered": covered, "generation_context_facts_total": total}
    metrics = derive.aggregate_retrieval([row("single", 1, 0, 1), row("combined", 0, 2, 2)])
    for k in (5, 20):
        values = metrics[f"at_{k}"]
        assert values["items"] == 1 and values["fact_evidence_coverage_items"] == 2
        assert values["fact_evidence_coverage"] == 0.5
        assert values["fact_evidence_coverage_micro"] == 2 / 3
    assert metrics["missing_qrels_items"] == ["combined"]
    unscorable = derive.aggregate_retrieval([row("combined", 0, 2, 2)])["at_5"]
    assert unscorable["micro_recall"] is None and unscorable["micro_f1"] is None
    assert unscorable["fact_evidence_coverage"] == 1


@pytest.fixture
def semantic_inputs():
    return (read(derive.RUN / "semantic-input.json"),
            read(derive.RUN / "semantic-assessment.json")["assessments"])


def test_duplicate_assessment_does_not_hide_a_missing_case(semantic_inputs):
    packet, judgments = semantic_inputs
    judgments[-1] = deepcopy(judgments[0])
    with pytest.raises(ValueError, match="Duplicate item_id"):
        assess.summarize_assessments(packet, judgments)


def test_assessment_quotes_and_indexes_must_match_actual_response(semantic_inputs):
    packet, judgments = semantic_inputs
    fact = next(f for row in judgments for f in row["facts"] if f["status"] == "covered")
    original = fact["response_quote"]
    fact["response_quote"] = "Invented response quote"
    with pytest.raises(ValueError, match="exact response quote"):
        assess.summarize_assessments(packet, judgments)
    fact["response_quote"] = original
    claim = next(c for row in judgments for c in row["claims"])
    claim["claim_index"] = True
    with pytest.raises(ValueError, match="must be an integer"):
        assess.summarize_assessments(packet, judgments)


def test_uncertain_semantic_judgment_cannot_pass(semantic_inputs):
    packet, judgments = semantic_inputs
    before = assess.summarize_assessments(packet, judgments)
    passing = set(before["full_rubric_pass"]["item_ids"])
    changed = next(row for row in judgments if row["item_id"] in passing and row["facts"])
    changed["facts"][0]["status"] = "uncertain"
    after = assess.summarize_assessments(packet, judgments)
    assert after["full_rubric_pass"]["passed"] == before["full_rubric_pass"]["passed"] - 1
    assert changed["item_id"] in after["uncertain_item_ids"]
