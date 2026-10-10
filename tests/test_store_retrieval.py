"""Meaningful local contracts; all vectors/scores here are deterministic fixtures."""

import hashlib
import json
import sqlite3

import numpy as np
import pytest

from parkguide.chunking import ENCODING, chunk_documents, chunk_statistics
from parkguide.retrieval import retrieve
from parkguide.store import activate_build, build_index, delete_document, get_manifest, integrity_report, load_documents, save_documents


def document(number=0, text=None, blocks=None, park="yose", page_type="html"):
    if blocks is None:
        blocks = [{"text": text or f"Visitor policy entry {number}: parking fees and accessible transport. special{number}", "kind": "paragraph", "heading_path": "Plan your visit > Fees"}]
    normalized = "\n\n".join(block["text"] for block in blocks)
    cursor = 0
    blocks = [dict(block) for block in blocks]
    for block in blocks:
        block["start"], block["end"] = cursor, cursor + len(block["text"])
        cursor = block["end"] + 2
    return {"doc_id": f"doc-{number:03d}", "source_url": f"https://www.nps.gov/{park}/planyourvisit/entry-{number}.{'pdf' if page_type == 'pdf' else 'htm'}", "content_hash": hashlib.sha256(normalized.encode()).hexdigest(), "title": f"Visitor policy {number}", "page_type": page_type, "effective_date": "2026-01-01" if number % 2 == 0 else None, "crawled_at": "2026-10-10T00:00:00+00:00", "normalized_text": normalized, "blocks": blocks, "normalized_blocks_json": json.dumps(blocks), "has_table": any(b["kind"] == "table" for b in blocks), "raw_sha256": "raw-fixture"}


def embeddings(texts):
    result = np.zeros((len(texts), 64), dtype=np.float32)
    for row in range(len(texts)):
        result[row, row % 64] = 3.0
    return result


@pytest.fixture
def indexed(tmp_path):
    db = tmp_path / "parkguide.sqlite"
    docs = [document(i, park="yose" if i < 16 else "yell", page_type="pdf" if i % 4 == 0 else "html") for i in range(32)]
    manifest = build_index(db, docs, "fixed", embeddings, model_config={"model": "fixture-v1", "dimension": 64})
    return db, docs, manifest


def test_final_acceptance_tracks_live_rows_not_only_original_manifest(indexed, tmp_path, monkeypatch):
    from parkguide import evaluation
    db,docs,manifest=indexed
    dataset=tmp_path/'test-items.jsonl'
    dataset.write_text('{"item_id":"fixture"}\n')
    monkeypatch.setattr(evaluation,'ROOT',tmp_path)
    monkeypatch.setattr(evaluation,'config',lambda:{'database':str(db)})
    variants=[{'name':'B3','build_id':manifest['build_id']}]
    original=evaluation.final_snapshot(dataset,variants)
    with sqlite3.connect(db) as connection:
        connection.execute('UPDATE embeddings SET vector_f32=? WHERE rowid=(SELECT min(rowid) FROM embeddings)',(np.zeros(64,dtype=np.float32).tobytes(),))
    changed=evaluation.final_snapshot(dataset,variants)
    assert changed!=original
    assert changed['builds']['B3']['manifest_hash']==original['builds']['B3']['manifest_hash']
    delete_document(db,docs[0]['doc_id'])
    deleted=evaluation.final_snapshot(dataset,variants)
    assert deleted!=changed and deleted['builds']['B3']['chunk_count']<changed['builds']['B3']['chunk_count']


@pytest.mark.parametrize("strategy", ["fixed", "structure"])
def test_unicode_chunk_limits_ids_and_original_evidence(strategy):
    doc = document(text=("Café visitors 東京 — transport and accessibility details. " * 90))
    chunks = chunk_documents([doc], strategy, target=80, overlap=16)
    assert len(chunks) > 3
    assert [c["chunk_id"] for c in chunks] == [c["chunk_id"] for c in chunk_documents([doc], strategy, 80, 16)]
    coverage = set()
    for chunk in chunks:
        assert chunk["token_count"] == len(ENCODING.encode(chunk["text"])) <= 80
        assert "�" not in chunk["text"]
        for span in chunk["source_spans"]:
            source = doc["normalized_text"][span["start"]:span["end"]]
            assert source in chunk["text"]
            coverage.update(range(span["start"], span["end"]))
    assert coverage == set(range(len(doc["normalized_text"])))
    assert chunk_statistics(chunks)["maximum"] <= 80


def test_table_headers_repeat_and_rows_are_preserved():
    table = "| Site | Fee |\n| --- | --- |\n" + "".join(f"| Campground {i} | ${i + 20} per night |\n" for i in range(20))
    doc = document(blocks=[{"text": table, "kind": "table", "heading_path": "Camping fees"}])
    chunks = chunk_documents([doc], "structure", 90, 10)
    assert len(chunks) > 2
    assert all("| Site | Fee |\n| --- | --- |\n" in c["text"] for c in chunks)
    for i in range(20):
        assert any(f"| Campground {i} | ${i + 20} per night |" in c["text"] for c in chunks)
    assert all(c["token_count"] <= 90 for c in chunks)


def test_heading_change_splits_structure_chunks():
    doc = document(blocks=[{"text": "First fee information.", "heading_path": "Fees", "kind": "paragraph"}, {"text": "Transport information.", "heading_path": "Transport", "kind": "paragraph"}])
    chunks = chunk_documents([doc], "structure")
    assert len(chunks) == 2
    assert {c["heading_path"] for c in chunks} == {"Fees", "Transport"}


def test_sqlite_roundtrip_preserves_source_bundle(tmp_path):
    db, doc = tmp_path / "test.sqlite", document()
    save_documents(db, [doc])
    loaded = load_documents(db)[0]
    assert loaded["normalized_text"] == doc["normalized_text"]
    assert loaded["blocks"] == doc["blocks"]
    assert loaded["raw_sha256"] == "raw-fixture"


def test_dense_filters_and_candidate_contract(indexed):
    db, _, _ = indexed
    vector = np.eye(64, dtype=np.float32)[0]
    result = retrieve(db, "parking fees", vector, "dense")
    assert result["candidate_count"] == 20
    assert len(result["final"]) == 5
    assert result["final"][0]["doc_id"] == "doc-000"
    filtered = retrieve(db, "parking fees", vector, filters={"park": "Yellowstone", "page_type": "pdf"})
    assert filtered["shortfall"] and filtered["candidate_count"] == 4
    assert all(c["page_type"] == "pdf" and "/yell/" in c["source_url"] for c in filtered["candidates"])
    comparison = retrieve(db, "parking fees", vector, filters={"parks": ["yose", "yell"]})
    assert comparison["eligible_count"] == 32
    date_filtered = retrieve(db, "parking fees", mode="bm25", filters={"effective_date": "2026-01-01"})
    assert date_filtered["eligible_count"] == 16


def test_bm25_and_rrf_have_visible_distinct_score_types(indexed):
    db, _, _ = indexed
    keyword = retrieve(db, "special7", mode="bm25")
    assert keyword["final"][0]["doc_id"] == "doc-007"
    result = retrieve(db, "special7", np.eye(64)[0], "hybrid")
    assert len(result["candidates"]) == 20
    for c in result["candidates"]:
        expected = sum(1 / (60 + rank) for rank in c["retriever_ranks"].values() if rank is not None)
        assert c["scores"]["rrf"] == pytest.approx(expected)
        assert c["scores"]["rerank"] is None


def test_visitor_subject_outranks_question_word_overlap(tmp_path):
    """A carried-dog query must find the pet rule, not short 'Can I' FAQs."""
    db = tmp_path / "visitor.sqlite"
    docs = [document(0, text="Pets are prohibited on the waterfall trail even if carried.")]
    docs += [document(i, text=f"Can I change my reservation? Call the campground office. Site {i}.")
             for i in range(1, 21)]
    docs += [document(i, text=f"Waterfall trail scenery and hiking distance. Viewpoint {i}.")
             for i in range(21, 31)]
    build_index(db, docs, "fixed", embeddings, model_config={"model": "fixture-v1", "dimension": 64})
    result = retrieve(db, "Can I carry my dog on the waterfall trail?", mode="bm25", filters={"parks": ["yose"]})
    assert result["final"][0]["doc_id"] == docs[0]["doc_id"]
    assert all("/yose/" in item["source_url"] for item in result["candidates"])


def test_lexical_cleanup_preserves_numbers_and_negation():
    from parkguide.retrieval import _tokens
    assert "not" in _tokens("Pets are not allowed on trails")
    assert {"25", "100"} <= set(_tokens("Stay 25 or 100 yards away"))


def test_followup_property_finds_rule_despite_long_prior_route(tmp_path):
    db = tmp_path / "followup.sqlite"
    docs = [document(0, text="Pets must be kept on a leash no longer than six feet.")]
    docs += [document(i, text=f"The paved road and unpaved trail around the lake offer a scenic walk. View {i}.")
             for i in range(1, 31)]
    build_index(db, docs, "fixed", embeddings, model_config={"model": "fixture-v1", "dimension": 64})
    query = "Yosemite: How long can his leash be? Previous topic: Can I walk my dog on the paved road to the lake And the unpaved trail around the lake"
    result = retrieve(db, query, np.eye(64)[1], filters={"parks": ["yose"]})
    assert docs[0]["doc_id"] in {item["doc_id"] for item in result["final"]}
    assert result["keyword_current_terms"] == ["leash"]
    assert result["keyword_query"].split().count("pet") == 1
    assert result["keyword_query"].split().count("lake") == 1
    # A route-only passage remains eligible through dense search, but does not
    # receive an extra RRF contribution for weak overlap with inherited context.
    route = next(item for item in result["candidates"] if item["doc_id"] == docs[1]["doc_id"])
    assert route["scores"]["bm25"] > 0
    assert route["retriever_ranks"] == {"bm25": None, "dense": 1}
    assert result["candidate_count"] == 20
    assert result["keyword_candidate_count"] == 1


def test_alternative_transport_retains_companion_restriction(tmp_path):
    db = tmp_path / "shuttle.sqlite"
    docs = [document(0, text="Pets are not permitted on park shuttle buses.", park="grca")]
    docs += [document(i, text=f"Ride the park shuttle bus to the viewpoint. Route {i}.", park="grca")
             for i in range(1, 31)]
    build_index(db, docs, "fixed", embeddings, model_config={"model": "fixture-v1", "dimension": 64})
    query = "Grand Canyon: Could we ride a park shuttle bus instead? Previous topic: Can I take my pet dog along the trails above the South Rim What if I carry him down an inner canyon trail below the rim"
    result = retrieve(db, query, mode="bm25", filters={"parks": ["grca"]})
    assert result["final"][0]["doc_id"] == docs[0]["doc_id"]
    assert result["keyword_query"].split().count("pet") == 1
    assert result["keyword_current_terms"] == ["shuttle", "bus"]


@pytest.mark.parametrize(("followup", "previous", "evidence"), [
    ("Can I bring him along?", "Can my dog ride a park shuttle?", "Pets are not permitted on park shuttle buses."),
    ("How long does it take?", "Tell me about the Lower Yosemite Fall trail.", "The Lower Yosemite Fall trail takes approximately 30 minutes."),
    ("Is that still allowed?", "Can I carry my dog on the trail to Vernal Fall?", "Pets are not permitted on the trail to Vernal Fall, even if carried."),
])
def test_generic_followup_retrieves_inherited_subject_without_gate(tmp_path, followup, previous, evidence):
    db = tmp_path / "generic.sqlite"
    docs = [document(0, text=evidence)]
    docs += [document(i, text=f"Visitor center parking lot and restroom information. Location {i}.")
             for i in range(1, 31)]
    build_index(db, docs, "fixed", embeddings, model_config={"model": "fixture-v1", "dimension": 64})
    result = retrieve(db, f"{followup} Previous topic: {previous}", mode="bm25", filters={"parks": ["yose"]})
    assert result["final"][0]["doc_id"] == docs[0]["doc_id"]
    assert result["keyword_current_terms"] == []
    assert result["keyword_candidate_count"] == 31


@pytest.mark.parametrize("followup", ["And how long?", "What about there?", "And in May 2027?", "And July 18th?", "What about Saturday?", "And at 4:30pm?", "Can I use it?", "Would that work?", "Can I go again?"])
def test_keyword_search_retains_topic_for_context_only_followups(followup):
    from parkguide.retrieval import _keyword_inputs
    query = followup + " Previous topic: visiting a campground with a generator"
    keywords, current_terms = _keyword_inputs(query, {"parks": ["yose"]})
    assert "generator" in keywords
    assert current_terms == []


def test_reranking_keeps_original_pool_and_full_post_order(indexed):
    db, _, _ = indexed
    result = retrieve(db, "parking", np.eye(64)[0], rerank=True, reranker=lambda pairs: np.arange(len(pairs)))
    before = [c["chunk_id"] for c in result["candidates"]]
    after = [c["chunk_id"] for c in result["reranked"]]
    assert after == list(reversed(before))
    assert all(c["scores"]["rerank"] is None for c in result["candidates"])
    assert len(result["reranked"]) == 20 and len(result["final"]) == 5
    assert result["final"][0]["pre_rank"] == 20
    assert result["final"][0]["post_rank"] == 1


def test_reranker_rejects_silent_pair_truncation_before_scoring(indexed):
    class Reranker:
        max_length = 512

        @staticmethod
        def tokenizer(left, right, **kwargs):
            assert kwargs["truncation"] is False
            return {"input_ids": [0] * 513}

        @staticmethod
        def predict(pairs, **kwargs):
            pytest.fail("Oversized pair must never reach model scoring")

    with pytest.raises(ValueError, match="silently truncated"):
        retrieve(indexed[0], "parking", mode="bm25", rerank=True, reranker=Reranker())


def test_repeated_build_reuses_vectors_without_cloud(indexed):
    db, docs, initial = indexed
    repeated = build_index(db, docs, "fixed", lambda _: pytest.fail("Reused index must not embed again"), model_config={"model": "fixture-v1", "dimension": 64})
    assert repeated["reused_existing"]
    assert repeated["build_id"] == initial["build_id"]
    assert integrity_report(db)["index_builds"] == 1


def test_failed_embedding_preserves_active_index(indexed):
    db, docs, initial = indexed
    before = integrity_report(db)
    with pytest.raises(ValueError, match="count/dimension"):
        build_index(db, docs, "structure", lambda texts: np.zeros((1, 64)))
    assert get_manifest(db)["build_id"] == initial["build_id"]
    assert integrity_report(db) == before


def test_import_failure_rolls_back_all_rows(indexed):
    db, docs, initial = indexed
    before = integrity_report(db)
    bad = dict(docs[0], doc_id="new-conflicting-id")
    with pytest.raises(sqlite3.IntegrityError):
        build_index(db, [bad], "structure", embeddings)
    assert integrity_report(db) == before
    assert get_manifest(db)["build_id"] == initial["build_id"]


def test_incomplete_build_cannot_replace_active_index(indexed):
    db, _, initial = indexed
    with sqlite3.connect(db) as connection:
        connection.execute("INSERT INTO index_builds VALUES ('incomplete', '{}', 0)")
        connection.execute("INSERT INTO chunks SELECT 'incomplete',chunk_id,doc_id,text,heading_path,source_span_json,token_count FROM chunks LIMIT 1")
    with pytest.raises(ValueError, match="incomplete"):
        activate_build(db, "incomplete")
    assert get_manifest(db)["build_id"] == initial["build_id"]


def test_offline_migration_and_baseline_retention(indexed):
    db, docs, baseline = indexed
    structure = build_index(db, docs, "structure", embeddings, activate=False)
    assert get_manifest(db)["build_id"] == baseline["build_id"]
    assert integrity_report(db)["index_builds"] == 2
    assert retrieve(db, "special7", mode="bm25", build_id=structure["build_id"])["candidate_count"] == 20
    migration = activate_build(db, structure["build_id"], delete_previous=True)
    assert migration["previous_build_rows_remaining"] == 0
    assert migration["integrity"]["orphan_vectors"] == 0
    assert migration["integrity"]["chunks_without_vectors"] == 0
    assert integrity_report(db)["index_builds"] == 1
    with pytest.raises(ValueError, match="No matching"):
        get_manifest(db, baseline["build_id"])


def test_document_delete_cascades_and_immediately_changes_retrieval(indexed):
    db, _, _ = indexed
    deletion = delete_document(db, "doc-007")
    assert deletion["deleted_documents"] == deletion["deleted_chunks"] == 1
    result = retrieve(db, "special7", mode="bm25")
    assert all(c["doc_id"] != "doc-007" for c in result["candidates"])
    assert integrity_report(db)["embeddings"] == 31
    assert integrity_report(db)["orphan_vectors"] == 0


@pytest.mark.parametrize("vector", [np.zeros(64), np.ones(63), np.full(64, np.nan)])
def test_invalid_query_vectors_are_rejected(indexed, vector):
    with pytest.raises(ValueError, match="Query embedding"):
        retrieve(indexed[0], "parking fees", vector, "dense")


def test_filter_shortfall_is_explicit_and_not_relaxed(indexed):
    result = retrieve(indexed[0], "parking", np.eye(64)[0], filters={"park": "grca"})
    assert result["final"] == [] and result["shortfall"]
    with pytest.raises(ValueError, match="Unknown metadata filter"):
        retrieve(indexed[0], "parking", mode="bm25", filters={"invented": True})
