import json

import pytest

from parkguide.budget import Budget
from parkguide.chat import answer, resolve_query
from parkguide.evaluation import evidence_covered, paired_bootstrap
from parkguide.guards import validate_answer


def test_switching_park_and_date_removes_old_constraints():
    query, filters = resolve_query("What about Yellowstone in October 2027?", [{"role": "user", "content": "Yosemite camping in July 2026"}])
    assert filters == {"parks": ["yell"]}
    assert "2026" not in query and "July" not in query and "Yosemite" not in query


def test_comparison_remembers_both_parks():
    _, filters = resolve_query("Compare their camping options", [{"role": "user", "content": "Yosemite camping?"}, {"role": "assistant", "content": "a prior real answer"}, {"role": "user", "content": "What about Yellowstone?"}])
    assert filters == {"parks": ["yose", "yell"]}


def test_quote_limit_is_per_page_not_per_chunk():
    words = [f"word{index}" for index in range(30)]
    contexts = [{"chunk_id": "c1", "doc_id": "d", "text": " ".join(words[:15])}, {"chunk_id": "c2", "doc_id": "d", "text": " ".join(words[15:])}]
    payload = {"action": "answer", "claims": [{"text": " ".join(words), "evidence_ids": ["c1", "c2"]}]}
    assert "quote_limit" in validate_answer(payload, contexts, {"d": " ".join(words)})


def test_unknown_citation_and_numerical_hallucination_are_rejected():
    contexts = [{"chunk_id": "c", "text": "The fee is 35 dollars."}]
    assert "number_without_source_witness" in validate_answer({"action": "answer", "claims": [{"text": "The fee is 50 dollars.", "evidence_ids": ["c"]}]}, contexts)
    assert "unknown_or_missing_citation" in validate_answer({"action": "answer", "claims": [{"text": "Fact", "evidence_ids": ["unknown"]}]}, contexts)


def test_evidence_coverage_combines_spans_without_wrong_page_credit():
    evidence = {"doc_id": "d", "start": 10, "end": 30}
    chunks = [{"doc_id": "d", "source_span": [{"start": 5, "end": 20}]}, {"doc_id": "d", "source_span": [{"start": 20, "end": 40}]}]
    assert evidence_covered(evidence, chunks)
    assert not evidence_covered(evidence, [{"doc_id": "other", "source_span": [{"start": 0, "end": 100}]}])
    assert not evidence_covered({**evidence, "content_hash": "old"}, [{"doc_id": "d", "content_hash": "new", "source_span": [{"start": 0, "end": 100}]}])


def test_missing_gold_stops_before_embedding_or_generation(monkeypatch):
    monkeypatch.setattr("parkguide.chat.gold_drafts_ready", lambda: False)
    def forbidden(*args, **kwargs):
        raise AssertionError("No model calls before draft gate")
    with pytest.raises(RuntimeError, match="40 source-based"):
        answer("question", generator=forbidden, embedder=forbidden)


def test_budget_reserves_before_calls_and_caps_across_instances(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/pricing.json").write_text(json.dumps({"generation": {"input_per_million_usd": 1000000, "output_per_million_usd": 0}}))
    first = Budget(tmp_path, cap=2)
    reservation = first.reserve("generation", 2)
    with pytest.raises(RuntimeError, match="cap reached"):
        Budget(tmp_path, cap=2).reserve("generation", 1)
    first.settle(reservation, 1)
    assert first.summary()["remaining_estimated_usd"] == 1


def test_paired_uncertainty_preserves_zero_difference():
    result = paired_bootstrap([0, 1, 1], [0, 1, 1], samples=100)
    assert result["ci95"] == [0, 0] and not result["established_lift"]
