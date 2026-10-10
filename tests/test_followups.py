"""Offline follow-up grounding contracts; no gold datasets or provider calls."""
import json
import re
from pathlib import Path
import sqlite3

import pytest

from parkguide import followups


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    db = tmp_path / "corpus.sqlite"
    url = "https://www.nps.gov/yose/planyourvisit/pets.htm"
    text = "Pets need a six-foot leash. Pets may use paved paths. Pets may not ride shuttle buses. Pets must be attended."
    entries = []
    for index, (question, quote) in enumerate([
        ("How long should my pet's leash be in Yosemite?", "Pets need a six-foot leash."),
        ("Which paths can my pet use in Yosemite?", "Pets may use paved paths."),
        ("Can my pet ride Yosemite shuttle buses?", "Pets may not ride shuttle buses."),
        ("May I leave my pet unattended in Yosemite?", "Pets must be attended."),
    ]):
        entries.append({"id": f"pets-{index}", "park": "yose", "topic": "pets", "question": question,
                        "source_url": url, "supporting_quote": quote, "keywords": ["pets", "dog", "leash"]})
    monkeypatch.setattr(followups, "load_catalog", lambda: entries)
    with sqlite3.connect(db) as connection:
        connection.executescript("""
        CREATE TABLE documents(doc_id TEXT, source_url TEXT, content_hash TEXT);
        CREATE TABLE index_builds(build_id TEXT, manifest_json TEXT, active INTEGER);
        CREATE TABLE chunks(build_id TEXT,chunk_id TEXT,doc_id TEXT,text TEXT,token_count INTEGER);
        """)
        connection.execute("INSERT INTO documents VALUES ('doc', ?, 'hash')", (url,))
        snapshot = json.dumps({"document_snapshot": {"doc": {"source_url": url, "content_hash": "hash"}}})
        connection.execute("INSERT INTO index_builds VALUES ('active', ?, 1)", (snapshot,))
        connection.execute("INSERT INTO index_builds VALUES ('old', ?, 0)", (snapshot,))
        connection.execute("INSERT INTO chunks VALUES ('active','evidence','doc',?,30)", (text,))
    return db, entries, url


def test_maximum_three_ranked_unique_relevant_supported_questions(corpus):
    db, entries, url = corpus
    suggestions = followups.suggest_questions(db, "active", "yose", "What are Yosemite's pet rules?", [{"source_url": url}], [])
    assert len(suggestions) == 3
    assert len({item["question"] for item in suggestions}) == 3
    for item in suggestions:
        resolved = followups.resolve_question(db, "active", "yose", item["question"])
        assert item["supporting_quote"] == resolved["supporting_quote"]
        assert item["evidence_ids"] == ["evidence"]


def test_excludes_asked_questions_and_dog_pet_paraphrases(corpus):
    db, entries, url = corpus
    suggestions = followups.suggest_questions(db, "active", "yose", "Can my dog ride Yosemite shuttle buses?", [{"source_url": url}],
                                              [{"role": "user", "content": entries[0]["question"]}])
    assert entries[0]["question"] not in [item["question"] for item in suggestions]
    assert entries[2]["question"] not in [item["question"] for item in suggestions]


def test_does_not_offer_unrelated_defaults(corpus):
    db, _, _ = corpus
    assert followups.suggest_questions(db, "active", "yose", "What fossils can I see?", [], []) == []


@pytest.mark.parametrize("mutation", ["missing", "changed_text", "stale_document", "oversized", "foreign_url"])
def test_suggestions_require_current_exact_bounded_support(corpus, mutation):
    db, entries, _ = corpus
    with sqlite3.connect(db) as connection:
        if mutation == "missing":
            connection.execute("DELETE FROM chunks")
        elif mutation == "changed_text":
            connection.execute("UPDATE chunks SET text='unrelated data'")
        elif mutation == "stale_document":
            connection.execute("UPDATE documents SET content_hash='changed'")
        elif mutation == "oversized":
            connection.execute("UPDATE chunks SET token_count=2000")
        else:
            for item in entries:
                item["source_url"] = "https://www.nps.gov/yell/planyourvisit/pets.htm"
    assert followups.supported_questions(db, "active", "yose") == []


def test_no_inactive_build_foreign_park_or_unknown_question(corpus):
    db, entries, _ = corpus
    assert followups.supported_questions(db, "old", "yose") == []
    assert followups.supported_questions(db, "active", "yell") == []
    assert followups.resolve_question(db, "active", "yose", "Invent a bear tour") is None
    assert followups.resolve_question(db, "active", "yose", entries[0]["question"] + " tomorrow") is None


def test_every_shipped_catalog_question_has_exact_active_corpus_support():
    root = Path(__file__).resolve().parents[1]
    db = root / "data/parkguide.sqlite"
    catalog = json.loads((root / "config/followup_questions.json").read_text())
    assert len({item["id"] for item in catalog}) == len(catalog)
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
        build = connection.execute("SELECT build_id FROM index_builds WHERE active=1").fetchone()[0]
        for park in followups.PARK_NAMES:
            supported = followups.supported_questions(db, build, park)
            assert {item["id"] for item in supported} == {item["id"] for item in catalog if item["park"] == park}
            for item in supported:
                assert followups.PARK_NAMES[park] in item["question"]
                text = connection.execute("SELECT text FROM chunks WHERE build_id=? AND chunk_id=?", (build, item["evidence_ids"][0])).fetchone()[0]
                assert item["supporting_quote"] in text


@pytest.mark.parametrize('entry', followups.load_catalog(), ids=lambda item: item['id'])
def test_catalog_questions_reach_answers_with_their_support_without_search_or_provider(entry):
    from parkguide import chat as core
    from parkguide.store import get_manifest
    db = followups.ROOT / 'data/parkguide.sqlite'
    build = get_manifest(db)['build_id']
    supported = followups.resolve_question(db, build, entry['park'], entry['question'])
    assert supported is not None

    def forbidden(*args, **kwargs):
        raise AssertionError('A provider or search was reached for a supported catalog question')

    def generator(question, contexts, history, **kwargs):
        assert contexts[0]['chunk_id'] == supported['evidence_ids'][0]
        assert entry['supporting_quote'] in contexts[0]['text']
        return {'action': 'answer', 'answer': '', 'claims': [{'text': 'An offline fixture answer using the supplied saved passage.', 'evidence_ids': supported['evidence_ids']}],
                'usage': {}, 'model': 'offline-fixture'}

    def reviewer(question, claims, contexts, history):
        # Keep each invented fixture witness within the existing 25-word limit.
        quote = entry['supporting_quote']
        words = list(re.finditer(r'\b\w+\b', quote))
        witnesses = [{'evidence_id': supported['evidence_ids'][0],
                      'quote': quote[words[start].start():words[min(start + 19, len(words) - 1)].end()]}
                     for start in range(0, len(words), 20)]
        return {'decisions': [{'claim_index': 0, 'supported': True, 'reason': 'Offline literal excerpt fixture.',
                'supporting_quotes': witnesses}], 'usage': {}}

    answer = core.answer(entry['question'], selected_park=entry['park'], build_id=build, followup_evidence_ids=supported['evidence_ids'],
                         generator=generator, reviewer=reviewer, embedder=forbidden, retriever=forbidden, enforce_gate=False, rerank=False)
    assert answer['response']['action'] == 'answer', answer.get('guard_errors')
    assert answer['response']['claims'][0]['evidence_ids'] == supported['evidence_ids']
