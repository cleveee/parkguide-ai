"""Conversation repair and source reuse contracts. All model replies are fixtures."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from parkguide.chat import answer, resolve_query
from parkguide.dialogue import detail_request, explanation_request, plan_dialogue, previous_evidence_ids, validate_plan
from parkguide.generation import GenerationError
from parkguide.retrieval import saved_evidence
from test_park_scope import forbidden, grounded_answer, payload, supported_review
from test_store_retrieval import indexed


@pytest.mark.parametrize("message", [
    "i dont understand", "I don't understand!", "Can you explain that more simply?",
    "the thing you just said, i need more info.", "Tell me more", "What do you mean?",
])
def test_repairs_keep_the_subject_across_multiple_turns(message):
    history = [{"role": "user", "content": "Are pets allowed on Yosemite trails?"},
               {"role": "assistant", "content": "A fixture answer."},
               {"role": "user", "content": "i dont understand"},
               {"role": "assistant", "content": "Which detail do you mean?"}]
    query, filters = resolve_query(message, history)
    assert "pets" in query and "trails" in query
    assert "understand" not in query and "thing" not in query
    assert filters == {"parks": ["yose"]}


def test_new_subject_after_confusion_drops_the_old_topic():
    query, _ = resolve_query("Where can I park my car?", [
        {"role": "user", "content": "Are pets allowed on trails?"},
        {"role": "user", "content": "i dont understand"}])
    assert "pets" not in query and "trails" not in query
    assert not explanation_request("Why are pets prohibited on trails?")


def test_requests_for_more_detail_search_instead_of_repeating_previous_evidence():
    history = [{'role': 'user', 'content': 'Are pets allowed on trails?'},
               {'role': 'assistant', 'content': 'A fixture answer.'}]
    result = grounded_answer('the thing you just said, i need more info.', history)
    assert result['dialogue']['action'] == 'search_followup'
    assert 'pets' in result['retrieval_query'] and 'thing' not in result['retrieval_query']
    assert not detail_request('Can you explain that more simply?')


def test_missing_previous_answer_clarifies_without_search_or_models():
    result = grounded_answer("I dont understand", embedder=forbidden, retriever=forbidden,
                             generator=forbidden, reviewer=forbidden)
    assert result['response']['action'] == 'clarify'
    assert result['response']['preflight_reason'] == 'missing_reference'


def search_plan(query):
    return {"action": "search_followup", "search_query": query, "clarification_kind": "none"}


def test_model_query_reaches_both_search_branches_with_companion_context():
    seen = []
    query = "Can a visitor with a dog use Yosemite park shuttles?"
    result = grounded_answer("Can we use a shuttle?", [
        {"role": "user", "content": "I'm visiting with my dog."},
        {"role": "assistant", "content": "A fixture answer."}],
        planner=lambda *args: search_plan(query), embedder=lambda texts: seen.extend(texts) or [[1.0]])
    assert seen == [query] and result['retrieval_query'] == query
    assert result['filters']['parks'] == ['yose']
    assert result['dialogue']['method'] == 'model'


def test_invalid_model_plan_falls_back_to_preserved_subject():
    def broken(*args):
        raise GenerationError("invalid_dialogue_plan")
    result = grounded_answer("i dont understand", [
        {"role": "user", "content": "Are pets allowed on trails?"},
        {"role": "assistant", "content": "A fixture answer."}], planner=broken)
    assert result['dialogue']['method'] == 'local_fallback'
    assert "pets" in result['retrieval_query']
    assert result['response']['action'] == 'answer'


def test_planner_budget_failure_is_not_bypassed():
    def exhausted(*args):
        raise RuntimeError("API budget cap reached; no request sent")
    with pytest.raises(RuntimeError, match="budget cap"):
        grounded_answer("Explain that", [{"role": "user", "content": "Pet rules?"},
                                        {"role": "assistant", "content": "A fixture answer."}], planner=exhausted)


def test_planner_cannot_switch_selected_park():
    result = grounded_answer("What about shuttles?", [
        {"role": "user", "content": "Yosemite pet rules?"},
        {"role": "assistant", "content": "A fixture answer."}],
        planner=lambda *args: search_plan("Yellowstone shuttle rules"))
    assert result['dialogue']['error'] == 'dialogue_query_outside_selected_park'
    assert result['filters']['parks'] == ['yose']


def test_reused_evidence_is_loaded_from_active_database_and_park(indexed):
    db, _, manifest = indexed
    from parkguide.store import _connection
    with _connection(db, readonly=True) as connection:
        identifiers = {row['doc_id']: row['chunk_id'] for row in connection.execute(
            "SELECT doc_id,chunk_id FROM chunks WHERE build_id=?", [manifest['build_id']])}
    identifier = identifiers['doc-000']
    trace = saved_evidence(db, [identifier], filters={'parks': ['yose']})
    assert trace['final'][0]['text'] and trace['evidence_reuse']
    assert saved_evidence(db, [identifier, 'stale-id'], filters={'parks': ['yose']}) is None
    assert saved_evidence(db, [identifiers['doc-020']], filters={'parks': ['yose']}) is None


def test_followup_lexical_gate_survives_a_semantic_query_rewrite(indexed):
    from parkguide.retrieval import retrieve
    db, _, _ = indexed
    trace = retrieve(db, 'A self-contained question about parking and transport', mode='bm25',
                     lexical_query='What about special15? Previous topic: Yosemite parking fees',
                     filters={'parks': ['yose']})
    assert trace['keyword_current_terms'] == ['special15']
    assert trace['candidates'] and all('special15' in item['text'] for item in trace['candidates'])


def test_old_evidence_is_not_reused_after_a_new_subject_refusal():
    history = [{"role": "assistant", "content": "Old answer", "evidence_ids": ['old-id']},
               {"role": "user", "content": "A new subject"},
               {"role": "assistant", "content": "No supporting information"}]
    assert previous_evidence_ids(history) == []


def test_explanation_reloads_sources_without_embedding_or_ranking(tmp_path, monkeypatch):
    from parkguide.runtime import config
    from parkguide.store import build_index, _connection
    from test_web import document, paragraph, vectors
    db = tmp_path / 'source.sqlite'
    manifest = build_index(db, [document('yose', 1, [paragraph('Pets must remain on a leash.')])],
                           'fixed', vectors, model_config={'model': 'fixture', 'dimension': 16})
    with _connection(db, readonly=True) as connection:
        identifier = connection.execute('SELECT chunk_id FROM chunks WHERE build_id=?', [manifest['build_id']]).fetchone()[0]
    settings = {**config(), 'database': str(db)}
    monkeypatch.setattr('parkguide.chat.config', lambda: settings)
    history = [{'role': 'user', 'content': 'What are the pet rules?'},
               {'role': 'assistant', 'content': 'A prior fixture answer.', 'evidence_ids': [identifier]}]
    result = answer('I dont understand', history, selected_park='yose', enforce_gate=False, rerank=False,
                    embedder=forbidden, generator=lambda *args, **kwargs: payload(evidence_ids=[identifier]),
                    reviewer=supported_review)
    assert result['retrieval']['evidence_reuse']
    assert result['response']['action'] == 'answer'
    assert result['dialogue']['reused_evidence_ids'] == [identifier]


@pytest.mark.parametrize("mutation", [
    {"search_query": ""}, {"search_query": "q\n"}, {"search_query": "x" * 1001},
    {"action": "execute"}, {"clarification_kind": "topic"},
])
def test_invalid_plans_cannot_reach_retrieval(mutation):
    with pytest.raises(GenerationError, match='invalid_dialogue_plan'):
        validate_plan({**search_plan('Pet rules'), **mutation})


def test_azure_planner_checks_pinned_model_and_usage(monkeypatch):
    from parkguide import dialogue
    response = SimpleNamespace(model='gpt-6-luna-2026-09-22',
        usage=SimpleNamespace(prompt_tokens=30, completion_tokens=20),
        choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(
            content=json.dumps(search_plan('Yosemite pet rules')), refusal=None))])
    client = SimpleNamespace(request=Mock(return_value=response), close=Mock(), model=response.model)
    monkeypatch.setattr(dialogue, 'Generator', lambda: client)
    result = plan_dialogue('What about trails?', [{'role': 'user', 'content': 'I have a dog.'}], 'yose')
    assert result['usage'] == {'input_tokens': 30, 'output_tokens': 20}
    assert client.close.called
    assert client.request.call_args.kwargs['timeout'] == 10.0
    response.model = 'unapproved-model'
    with pytest.raises(GenerationError, match='returned_model_differs') as error:
        plan_dialogue('What about trails?', [], 'yose')
    assert error.value.usage == {'input_tokens': 30, 'output_tokens': 20}
