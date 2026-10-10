"""Local SQLite index builds with atomic activation and cascading deletion."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np

from .chunking import CHUNKER_VERSION, canonical_hash, chunk_documents, chunk_statistics, unpack_document


@contextmanager
def _connection(db):
    connection = sqlite3.connect(str(db), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(db):
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    with _connection(db) as connection:
        connection.executescript(Path(__file__).with_name("schema.sql").read_text())
        connection.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version', '1')")


def _save_documents(connection, docs):
    for original in docs:
        doc = unpack_document(original)
        bundle = {"normalized_text": doc["normalized_text"], "blocks": doc["blocks"], "has_table": doc.get("has_table", any(b.get("kind") == "table" for b in doc["blocks"])), "raw_sha256": doc.get("raw_sha256")}
        values = [doc[key] for key in ("doc_id", "source_url", "content_hash", "title", "page_type")]
        values += [doc.get("effective_date"), doc["crawled_at"], json.dumps(bundle, ensure_ascii=False, sort_keys=True)]
        connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(doc_id) DO UPDATE SET source_url=excluded.source_url, content_hash=excluded.content_hash, title=excluded.title, page_type=excluded.page_type, effective_date=excluded.effective_date, crawled_at=excluded.crawled_at, normalized_blocks_json=excluded.normalized_blocks_json", values)


def save_documents(db, docs):
    docs = list(docs)
    initialize(db)
    with _connection(db) as connection:
        _save_documents(connection, docs)
    return {"saved": len(docs)}


def load_documents(db):
    with _connection(db) as connection:
        return [unpack_document(dict(row)) for row in connection.execute("SELECT * FROM documents ORDER BY doc_id")]


def load_chunks(db, build_id=None):
    """Read a complete immutable build for qrels/reproduction without ranking."""
    manifest = get_manifest(db, build_id)
    with _connection(db) as connection:
        rows = connection.execute("SELECT * FROM chunks WHERE build_id=? ORDER BY chunk_id", (manifest["build_id"],)).fetchall()
    chunks = []
    for row in rows:
        chunk = dict(row)
        chunk.update(manifest["document_snapshot"][chunk["doc_id"]])
        chunk["source_spans"] = json.loads(chunk["source_span_json"])
        chunk["source_span"] = chunk["source_spans"]
        chunks.append(chunk)
    return chunks


def _activate(connection, build_id, delete_previous):
    if not connection.execute("SELECT 1 FROM index_builds WHERE build_id=?", (build_id,)).fetchone():
        raise ValueError("Unknown index build")
    chunk_count = connection.execute("SELECT count(*) FROM chunks WHERE build_id=?", (build_id,)).fetchone()[0]
    vector_count = connection.execute("SELECT count(*) FROM embeddings WHERE build_id=?", (build_id,)).fetchone()[0]
    if not chunk_count or chunk_count != vector_count:
        raise ValueError("Cannot activate an empty or incomplete index")
    previous = [row[0] for row in connection.execute("SELECT build_id FROM index_builds WHERE active=1 AND build_id != ?", (build_id,))]
    previous_ids = [row[0] for prior in previous for row in connection.execute("SELECT chunk_id FROM chunks WHERE build_id=?", (prior,))]
    connection.execute("UPDATE index_builds SET active=0 WHERE active=1")
    connection.execute("UPDATE index_builds SET active=1 WHERE build_id=?", (build_id,))
    if delete_previous:
        for prior in previous:
            connection.execute("DELETE FROM index_builds WHERE build_id=?", (prior,))
    return {"previous_builds": previous, "previous_chunk_ids": previous_ids, "deleted_previous": bool(delete_previous), "active_build": build_id}


def activate_build(db, build_id, delete_previous=False):
    with _connection(db) as connection:
        migration = _activate(connection, build_id, delete_previous)
    migration["integrity"] = integrity_report(db)
    if delete_previous:
        with _connection(db) as connection:
            migration["previous_build_rows_remaining"] = sum(connection.execute("SELECT count(*) FROM chunks WHERE build_id=?", (prior,)).fetchone()[0] for prior in migration["previous_builds"])
    return migration


def build_index(db, docs, strategy, embedder, *, model_config=None, target=200, overlap=40, activate=True, delete_previous=False):
    """Embed outside the transaction; atomically import only a complete build."""
    docs = [unpack_document(doc) for doc in docs]
    chunks = chunk_documents(docs, strategy, target, overlap)
    if not chunks:
        raise ValueError("Cannot build an empty index")
    identity = {
        "corpus": sorted((d["doc_id"], d["content_hash"]) for d in docs),
        "chunker": {"strategy": strategy, "target": target, "overlap": overlap, "version": CHUNKER_VERSION, "tokenizer": "cl100k_base"},
        "embedding": dict(model_config or {"model": "unspecified"}),
        "distance": "cosine", "normalization": "l2", "dtype": "float32",
        "ordered_chunk_ids_sha256": canonical_hash([c["chunk_id"] for c in chunks]),
    }
    build_id = canonical_hash(identity)
    initialize(db)
    with _connection(db) as connection:
        existing = connection.execute("SELECT manifest_json FROM index_builds WHERE build_id=?", (build_id,)).fetchone()
        if existing:
            manifest = json.loads(existing[0])
            counts = connection.execute("SELECT (SELECT count(*) FROM chunks WHERE build_id=?), (SELECT count(*) FROM embeddings WHERE build_id=?)", (build_id, build_id)).fetchone()
            if tuple(counts) != (len(chunks), len(chunks)):
                raise ValueError("Existing immutable build is incomplete; delete it explicitly before rebuilding")
            if activate:
                manifest = dict(manifest, migration=_activate(connection, build_id, delete_previous))
            manifest["reused_existing"] = True
            return manifest
    vectors = np.asarray(embedder([chunk["text"] for chunk in chunks]), dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != len(chunks) or not vectors.shape[1]:
        raise ValueError("Embedding count/dimension does not match chunks")
    expected_dimension = (model_config or {}).get("dimension")
    if expected_dimension and vectors.shape[1] != expected_dimension:
        raise ValueError("Embedding dimension differs from model configuration")
    if not np.isfinite(vectors).all():
        raise ValueError("Embedding vectors contain nonfinite values")
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms == 0) or not np.isfinite(norms).all():
        raise ValueError("Embedding vectors have invalid norms")
    vectors = np.ascontiguousarray(vectors / norms[:, None], dtype="<f4")
    manifest = {
        "build_id": build_id, "identity": identity, "strategy": strategy,
        "created_at": datetime.now(timezone.utc).isoformat(), "dimension": vectors.shape[1],
        "vector_sha256": hashlib.sha256(vectors.tobytes()).hexdigest(),
        "ordered_chunk_ids_sha256": canonical_hash([c["chunk_id"] for c in chunks]),
        "chunk_ids": [c["chunk_id"] for c in chunks], "statistics": chunk_statistics(chunks),
        "document_snapshot": {d["doc_id"]: {key: d.get(key) for key in ("source_url", "title", "page_type", "effective_date", "crawled_at", "content_hash")} for d in docs},
    }
    with _connection(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _save_documents(connection, docs)
        connection.execute("INSERT INTO index_builds VALUES (?, ?, 0)", (build_id, json.dumps(manifest, sort_keys=True)))
        connection.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?)", [(build_id, c["chunk_id"], c["doc_id"], c["text"], c["heading_path"], c["source_span_json"], c["token_count"]) for c in chunks])
        connection.executemany("INSERT INTO embeddings VALUES (?, ?, ?, ?)", [(build_id, c["chunk_id"], vectors.shape[1], vectors[i].tobytes()) for i, c in enumerate(chunks)])
        if activate:
            manifest["migration"] = _activate(connection, build_id, delete_previous)
    manifest["integrity"] = integrity_report(db)
    return manifest


def get_manifest(db, build_id=None):
    with _connection(db) as connection:
        row = connection.execute("SELECT manifest_json FROM index_builds WHERE build_id=?" if build_id else "SELECT manifest_json FROM index_builds WHERE active=1", (build_id,) if build_id else ()).fetchone()
        if not row:
            raise ValueError("No matching active index; build and activate an index first")
        return json.loads(row[0])


def delete_document(db, doc_id):
    with _connection(db) as connection:
        affected = connection.execute("SELECT count(*) FROM chunks WHERE doc_id=?", (doc_id,)).fetchone()[0]
        removed = connection.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,)).rowcount
    return {"deleted_documents": removed, "deleted_chunks": affected, "integrity": integrity_report(db)}


def delete_build(db, build_id):
    with _connection(db) as connection:
        removed = connection.execute("DELETE FROM index_builds WHERE build_id=?", (build_id,)).rowcount
    return {"deleted_builds": removed, "integrity": integrity_report(db)}


def integrity_report(db):
    with _connection(db) as connection:
        counts = {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("documents", "index_builds", "chunks", "embeddings")}
        counts["foreign_key_errors"] = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        counts["orphan_vectors"] = connection.execute("SELECT count(*) FROM embeddings e LEFT JOIN chunks c ON c.build_id=e.build_id AND c.chunk_id=e.chunk_id WHERE c.chunk_id IS NULL").fetchone()[0]
        counts["chunks_without_vectors"] = connection.execute("SELECT count(*) FROM chunks c LEFT JOIN embeddings e ON c.build_id=e.build_id AND c.chunk_id=e.chunk_id WHERE e.chunk_id IS NULL").fetchone()[0]
        counts["active_builds"] = connection.execute("SELECT count(*) FROM index_builds WHERE active=1").fetchone()[0]
        return counts
