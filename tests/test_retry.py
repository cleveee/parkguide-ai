"""Azure retry timing and reservation accounting with no network or real sleep."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from parkguide.chat import answer, paid_claim_review
from parkguide.generation import GenerationError
from parkguide.runtime import config


CONTEXTS = [{"chunk_id": "retry-fixture", "doc_id": "retry-fixture-doc",
             "source_url": "https://www.nps.gov/yose/planyourvisit/fixture-pets.htm",
             "text": "Pets must remain on a leash.", "title": "Invented retry fixture"}]
CLAIMS = [{"text": "Dogs require leashes.", "evidence_ids": ["retry-fixture"]}]
GOOD_USAGE = {"input_tokens": 13, "output_tokens": 5}
ERROR_USAGE = {"input_tokens": 7, "output_tokens": 2}


def forbidden(*args, **kwargs):
    raise AssertionError("Retry contract tests cannot access a provider or database")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr("parkguide.generation.OpenAI", forbidden)
    monkeypatch.setattr("parkguide.chat.cached_embed", forbidden)
    monkeypatch.setattr("parkguide.retrieval.retrieve", forbidden)


def supported(*args, **kwargs):
    return {"decisions": [{"claim_index": 0, "supported": True, "reason": "Synthetic leash-rule witness.",
                           "supporting_quotes": [{"evidence_id": "retry-fixture", "quote": CONTEXTS[0]["text"]}]}],
            "usage": deepcopy(GOOD_USAGE)}


def success(path):
    if path == "review":
        return supported()
    return {"action": "answer", "answer": CLAIMS[0]["text"], "claims": deepcopy(CLAIMS),
            "usage": deepcopy(GOOD_USAGE), "elapsed_ms": 0}


def invoke(path, outcomes, monkeypatch):
    provider = Mock(side_effect=outcomes)
    if path == "review":
        monkeypatch.setattr("parkguide.claim_review.review_claims", provider)
        runner = lambda: paid_claim_review("Pet rules?", CLAIMS, CONTEXTS, [], config())
    else:
        monkeypatch.setattr("parkguide.generation.generate", provider)
        trace = {"candidates": CONTEXTS, "final": CONTEXTS, "candidate_count": 1, "timings": {}}
        runner = lambda: answer("Pet rules?", selected_park="yose", enforce_gate=False,
                                embedder=lambda questions: [[1.0]],
                                retriever=lambda *args, **kwargs: deepcopy(trace),
                                reviewer=supported, rerank=False)
    return runner, provider


def ledger(monkeypatch):
    budget = SimpleNamespace(reserve=Mock(side_effect=["r1", "r2", "r3"]), settle=Mock(return_value=0.001))
    monkeypatch.setattr("parkguide.chat.Budget", lambda: budget)
    return budget


@pytest.mark.parametrize("path", ["generation", "review"])
@pytest.mark.parametrize("hint,expected_wait", [(7.5, 7.5), (0, 1), (None, 60)])
def test_both_paths_honor_retry_hints_and_settle_each_attempt_once(path, hint, expected_wait, monkeypatch):
    error = GenerationError("provider_http_error", status_code=429, usage=deepcopy(ERROR_USAGE), retry_after_seconds=hint)
    budget = ledger(monkeypatch)
    sleep = Mock()
    monkeypatch.setattr("parkguide.chat.time.sleep", sleep)
    runner, provider = invoke(path, [error, success(path)], monkeypatch)
    result = runner()
    assert provider.call_count == 2 and budget.reserve.call_count == 2
    sleep.assert_called_once_with(expected_wait)
    assert budget.settle.call_args_list == [call("r1", 7, 2, error=True), call("r2", 13, 5)]
    assert (result["decisions"][0]["supported"] if path == "review" else result["response"]["action"] == "answer")


@pytest.mark.parametrize("path", ["generation", "review"])
def test_long_retry_hint_stops_without_sleeping_or_reserving_another_call(path, monkeypatch):
    error = GenerationError("provider_http_error", status_code=429, usage=deepcopy(ERROR_USAGE), retry_after_seconds=61)
    budget = ledger(monkeypatch)
    sleep = Mock()
    monkeypatch.setattr("parkguide.chat.time.sleep", sleep)
    runner, provider = invoke(path, [error], monkeypatch)
    with pytest.raises(GenerationError) as rejected:
        runner()
    assert rejected.value is error
    provider.assert_called_once()
    budget.reserve.assert_called_once()
    budget.settle.assert_called_once_with("r1", 7, 2, error=True)
    sleep.assert_not_called()


@pytest.mark.parametrize("path", ["generation", "review"])
def test_retry_exhaustion_keeps_all_three_settlements_and_stops_at_two_retries(path, monkeypatch):
    errors = [GenerationError("provider_http_error", status_code=429, usage=deepcopy(ERROR_USAGE), retry_after_seconds=3)
              for _ in range(3)]
    budget = ledger(monkeypatch)
    sleep = Mock()
    monkeypatch.setattr("parkguide.chat.time.sleep", sleep)
    runner, provider = invoke(path, errors, monkeypatch)
    with pytest.raises(GenerationError) as rejected:
        runner()
    assert rejected.value is errors[-1]
    assert provider.call_count == 3 and budget.reserve.call_count == 3
    assert sleep.call_args_list == [call(3), call(3)]
    assert budget.settle.call_args_list == [call(f"r{i}", 7, 2, error=True) for i in range(1, 4)]


@pytest.mark.parametrize("path", ["generation", "review"])
def test_unknown_failed_usage_is_preserved_as_unknown_in_reservation_settlement(path, monkeypatch):
    error = GenerationError("provider_http_error", status_code=429, retry_after_seconds=2)
    budget = ledger(monkeypatch)
    monkeypatch.setattr("parkguide.chat.time.sleep", Mock())
    runner, _ = invoke(path, [error, success(path)], monkeypatch)
    runner()
    assert budget.settle.call_args_list == [call("r1", None, 0, error=True), call("r2", 13, 5)]


@pytest.mark.parametrize("path", ["generation", "review"])
def test_transient_server_errors_use_bounded_backoff_and_preserve_each_attempt(path, monkeypatch):
    errors = [GenerationError("provider_http_error", status_code=503, usage=deepcopy(ERROR_USAGE)) for _ in range(2)]
    budget = ledger(monkeypatch)
    sleep = Mock()
    monkeypatch.setattr("parkguide.chat.time.sleep", sleep)
    runner, provider = invoke(path, [*errors, success(path)], monkeypatch)
    runner()
    assert provider.call_count == 3 and budget.reserve.call_count == 3
    assert sleep.call_args_list == [call(1), call(2)]
    assert budget.settle.call_args_list == [call("r1", 7, 2, error=True), call("r2", 7, 2, error=True), call("r3", 13, 5)]


@pytest.mark.parametrize("path", ["generation", "review"])
def test_credential_failures_settle_once_and_never_retry(path, monkeypatch):
    error = GenerationError("provider_http_error", status_code=401)
    budget = ledger(monkeypatch)
    sleep = Mock()
    monkeypatch.setattr("parkguide.chat.time.sleep", sleep)
    runner, provider = invoke(path, [error], monkeypatch)
    with pytest.raises(GenerationError) as rejected:
        runner()
    assert rejected.value is error
    provider.assert_called_once()
    budget.reserve.assert_called_once()
    budget.settle.assert_called_once_with("r1", None, 0, error=True)
    sleep.assert_not_called()
