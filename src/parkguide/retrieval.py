"""Exact local dense/BM25 retrieval, rank fusion, and optional CPU reranking."""

from __future__ import annotations

import json
from pathlib import Path
import re
from time import perf_counter
from urllib.parse import urlparse

import numpy as np
from rank_bm25 import BM25Okapi

from .store import _connection, get_manifest

PARK_CODES = {"yosemite": "yose", "yellowstone": "yell", "grand canyon": "grca", "grandcanyon": "grca"}
DEFAULT_RERANKER = "cross-encoder/ms-marco-MiniLM-L6-v2"
DEFAULT_RERANKER_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
_RERANKERS = {}


def _tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _park(url):
    return urlparse(url).path.strip("/").split("/")[0].lower()


def _eligible(chunk, filters):
    for field, expected in (filters or {}).items():
        if field not in {"park", "parks", "page_type", "doc_id", "source_url", "effective_date", "effective_date_from", "effective_date_to"}:
            raise ValueError(f"Unknown metadata filter: {field}")
        values = expected if isinstance(expected, (tuple, list, set)) else [expected]
        if field in {"park", "parks"}:
            if _park(chunk["source_url"]) not in [PARK_CODES.get(str(v).lower(), str(v).lower()) for v in values]:
                return False
        elif field in {"effective_date_from", "effective_date_to"}:
            date = chunk.get("effective_date")
            if not date or (field.endswith("from") and date < expected) or (field.endswith("to") and date > expected):
                return False
        elif chunk.get(field) not in values:
            return False
    return True


def load_reranker(model=DEFAULT_RERANKER, revision=None):
    if revision is None:
        configuration = Path(__file__).resolve().parents[2] / "config/project.json"
        if configuration.exists():
            approved = json.loads(configuration.read_text()).get("retrieval", {})
            if approved.get("reranker") == model:
                revision = approved.get("reranker_revision")
        if revision is None and model == DEFAULT_RERANKER:
            revision = DEFAULT_RERANKER_REVISION
    key = (model, revision)
    if key not in _RERANKERS:
        try:
            from sentence_transformers import CrossEncoder
            from torch import nn
        except ImportError as exc:
            raise RuntimeError("Install the approved optional rerank extra before reranking") from exc
        _RERANKERS[key] = CrossEncoder(model, revision=revision, device="cpu", max_length=512, activation_fn=nn.Identity())
    return _RERANKERS[key]


def retrieve(db, query, query_vector=None, mode="hybrid", build_id=None, filters=None, rerank=False, reranker=None, *, candidate_count=20, per_retriever_fetch=40, final_count=5, rrf_k=60):
    if mode not in {"bm25", "dense", "hybrid"}:
        raise ValueError("Retrieval mode must be bm25, dense, or hybrid")
    if candidate_count < 20 or not 1 <= final_count <= 5 or per_retriever_fetch < candidate_count:
        raise ValueError("Require >=20 candidates, fetch >= candidates, and 1–5 final contexts")
    if not query.strip():
        raise ValueError("Retrieval query cannot be empty")
    if rrf_k < 0:
        raise ValueError("RRF constant must be nonnegative")
    unknown = set(filters or {}) - {"park", "parks", "page_type", "doc_id", "source_url", "effective_date", "effective_date_from", "effective_date_to"}
    if unknown:
        raise ValueError(f"Unknown metadata filter: {sorted(unknown)[0]}")
    total_start = perf_counter()
    manifest = get_manifest(db, build_id)
    build_id = manifest["build_id"]
    with _connection(db) as connection:
        rows = connection.execute("SELECT c.*, e.dimension, e.vector_f32 FROM chunks c JOIN embeddings e USING(build_id,chunk_id) WHERE c.build_id=? ORDER BY c.chunk_id", (build_id,)).fetchall()
    chunks, vectors = [], []
    for row in rows:
        chunk = dict(row)
        dimension, blob = chunk.pop("dimension"), chunk.pop("vector_f32")
        chunk.update(manifest["document_snapshot"][chunk["doc_id"]])
        chunk["source_spans"] = json.loads(chunk["source_span_json"])
        chunk["source_span"] = chunk["source_spans"]
        if _eligible(chunk, filters):
            chunks.append(chunk)
            vectors.append(np.frombuffer(blob, dtype="<f4", count=dimension))
    load_ms = (perf_counter() - total_start) * 1000
    start = perf_counter()
    if not chunks:
        return {"build_id": build_id, "mode": mode, "candidates": [], "reranked": [], "final": [], "candidate_count": 0, "eligible_count": 0, "shortfall": True, "requested_candidates": candidate_count, "timings": {"load_ms": load_ms, "retrieval_ms": 0.0, "rerank_ms": 0.0, "total_ms": (perf_counter() - total_start) * 1000}, "filters": filters or {}}
    bm25_scores = np.zeros(len(chunks))
    dense_scores = np.zeros(len(chunks))
    ranks = {}

    def rank(scores):
        return sorted(range(len(chunks)), key=lambda i: (-float(scores[i]), chunks[i]["chunk_id"]))[:per_retriever_fetch]

    if mode in {"bm25", "hybrid"}:
        corpus_tokens = [_tokens(chunk["text"]) or ["__empty__"] for chunk in chunks]
        bm25_scores = BM25Okapi(corpus_tokens).get_scores(_tokens(query))
        ranks["bm25"] = rank(bm25_scores)
    if mode in {"dense", "hybrid"}:
        vector = np.asarray(query_vector, dtype=np.float32)
        if vector.shape != (manifest["dimension"],) or not np.isfinite(vector).all():
            raise ValueError("Query embedding dimension/values do not match index")
        norm = np.linalg.norm(vector)
        if not np.isfinite(norm) or norm == 0:
            raise ValueError("Query embedding has invalid norm")
        dense_scores = np.stack(vectors) @ (vector / norm)
        ranks["dense"] = rank(dense_scores)
    if mode == "hybrid":
        fusion = {}
        for order in ranks.values():
            for position, idx in enumerate(order, start=1):
                fusion[idx] = fusion.get(idx, 0.0) + 1.0 / (rrf_k + position)
        indices = sorted(fusion, key=lambda i: (-fusion[i], chunks[i]["chunk_id"]))[:candidate_count]
    else:
        fusion = {}
        indices = ranks[mode][:candidate_count]
    rank_maps = {name: {idx: position for position, idx in enumerate(order, start=1)} for name, order in ranks.items()}
    candidates = []
    for position, idx in enumerate(indices, start=1):
        candidate = dict(chunks[idx], pre_rank=position, rank=position)
        candidate["scores"] = {"bm25": float(bm25_scores[idx]) if "bm25" in ranks else None, "dense": float(dense_scores[idx]) if "dense" in ranks else None, "rrf": fusion.get(idx), "rerank": None}
        candidate["retriever_ranks"] = {name: lookup.get(idx) for name, lookup in rank_maps.items()}
        candidate["score"] = fusion[idx] if mode == "hybrid" else candidate["scores"][mode]
        candidates.append(candidate)
    retrieval_ms = (perf_counter() - start) * 1000
    start = perf_counter()
    reranked = [dict(candidate, scores=dict(candidate["scores"])) for candidate in candidates]
    if rerank:
        scorer = reranker or load_reranker()
        pairs = [(query, candidate["text"]) for candidate in reranked]
        if hasattr(scorer, "tokenizer"):
            maximum = getattr(scorer, "max_length", None) or min(getattr(scorer.tokenizer, "model_max_length", 512), 512)
            pair_lengths = [len(scorer.tokenizer(left, right, truncation=False, add_special_tokens=True)["input_ids"]) for left, right in pairs]
            if any(length > maximum for length in pair_lengths):
                raise ValueError(f"Reranker input would be silently truncated: longest pair {max(pair_lengths)} tokens, limit {maximum}; shorten query or rechunk explicitly")
        else:
            pair_lengths = None
        scores = scorer(pairs) if callable(scorer) and not hasattr(scorer, "predict") else scorer.predict(pairs, show_progress_bar=False)
        scores = np.asarray(scores, dtype=float).reshape(-1)
        if scores.shape != (len(reranked),) or not np.isfinite(scores).all():
            raise ValueError("Reranker returned invalid candidate scores")
        for candidate, score in zip(reranked, scores):
            candidate["scores"]["rerank"] = float(score)
            candidate["score"] = float(score)
        reranked.sort(key=lambda c: (-c["score"], c["chunk_id"]))
    for position, candidate in enumerate(reranked, start=1):
        candidate["rank"] = position
        candidate["post_rank"] = position
    rerank_ms = (perf_counter() - start) * 1000
    return {"build_id": build_id, "mode": mode, "candidates": candidates, "reranked": reranked, "final": reranked[:final_count], "candidate_count": len(candidates), "eligible_count": len(chunks), "shortfall": len(candidates) < candidate_count, "requested_candidates": candidate_count, "filters": filters or {}, "rerank_input_tokens": pair_lengths if rerank else None, "score_types": {"dense": "cosine", "bm25": "BM25Okapi", "rrf": f"sum(1/({rrf_k}+rank))", "rerank": "raw model score (not calibrated probability)"}, "timings": {"load_ms": load_ms, "retrieval_ms": retrieval_ms, "rerank_ms": rerank_ms if rerank else 0.0, "total_ms": (perf_counter() - total_start) * 1000}}
