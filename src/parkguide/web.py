"""FastAPI bridge for the ParkGuide web app (local loopback or Vercel profile).

The browser calls only same-origin /api/*: on 127.0.0.1:8513 locally, or on the
allow-listed Vercel/custom-domain host when hosted (see runtime.py). This process alone
reads SQLite and reaches Azure, always through the shared parkguide.chat.answer
path with a mandatory selected park. It never initializes or rebuilds the corpus
or vectors, and returns only reviewed output, validated stored evidence, safe
operational diagnostics and measured values.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from typing import Annotated, Any, Literal
import uuid

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import chat as core
from . import embedding_cache
from .runtime import ROOT, config, hosted, ledger_path as runtime_ledger_path, rerank_override, runtime_profile, sqlite_uri
from .source_links import captured_label, cited_source_pages, official_source_url

HOST = "127.0.0.1"
PORT = 8513
# Hosted: the build copies web/dist to public/ (CDN); the function keeps the shell.
DIST = ROOT / ("public" if hosted() else "web/dist")
ALLOWED_HOSTS = {f"{HOST}:{PORT}", f"localhost:{PORT}"}
# Vite's development server (5173) proxies /api here only when explicitly enabled.
DEV_HOSTS = {"127.0.0.1:5173", "localhost:5173"}
MAX_BODY_BYTES = 64 * 1024
MAX_QUESTION_CHARS = 1000
MAX_HISTORY_MESSAGES = 12
MAX_HISTORY_CONTENT_CHARS = 4000
PARK_CODES = tuple(core.PARK_NAMES)
SCORE_LABELS = {
    "dense": "Cosine similarity (query vs. stored vector)",
    "bm25": "BM25 Okapi lexical score",
    "rrf": "Reciprocal-rank fusion, sum of 1/(60 + rank)",
    "rerank": "Cross-encoder reranker raw score (not a probability)",
}
_ID = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_SAFE_MESSAGE = re.compile(r"^[A-Za-z0-9 _.,;:()'/-]{1,160}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Lowercase DNS hostname, at least two labels, no port, wildcard or userinfo.
_HOSTNAME = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")

log = logging.getLogger("parkguide.web")
# One paid answer at a time per process keeps budget reservations and the
# Azure call sequence simple. A second request is refused, never queued.
_ANSWER_LOCK = threading.Lock()


class WebError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(code)
        self.status, self.code, self.message, self.details = status, code, message, details


def database() -> Path:
    return ROOT / config()["database"]


def ledger_path() -> Path:
    """The budget ledger written by parkguide.budget.Budget for this profile."""
    return runtime_ledger_path()


def hosted_hosts() -> set[str]:
    """Exact HTTPS hosts from server-side env only; never from request headers.

    VERCEL_URL and VERCEL_PROJECT_PRODUCTION_URL are bare hostnames set by
    Vercel. PARKGUIDE_PUBLIC_ORIGIN is an optional exact https://host origin
    for a custom domain. Malformed values are ignored, not widened.
    """
    hosts = set()
    for name in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        value = os.environ.get(name, "").strip()
        if _HOSTNAME.match(value):
            hosts.add(value)
    origin = os.environ.get("PARKGUIDE_PUBLIC_ORIGIN", "").strip()
    if origin.startswith("https://") and _HOSTNAME.match(origin[len("https://"):]):
        hosts.add(origin[len("https://"):])
    return hosts


def _allowed_hosts() -> set[str]:
    if hosted():
        return hosted_hosts()
    return ALLOWED_HOSTS | (DEV_HOSTS if os.environ.get("PARKGUIDE_WEB_DEV") == "1" else set())


def _allowed_origins() -> set[str]:
    scheme = "https" if hosted() else "http"
    return {f"{scheme}://{host}" for host in _allowed_hosts()}


@contextmanager
def _connect():
    """Read-only SQLite access; a missing database is an error, never created."""
    path = database()
    if not path.is_file():
        raise WebError(503, "database_missing", "The SQLite database is missing.")
    connection = sqlite3.connect(sqlite_uri(path), uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _finite(value: Any) -> Any:
    """Recursively replace NaN/inf with None so no invalid JSON is produced."""
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(item) for item in value]
    if hasattr(value, "item"):  # NumPy scalar
        return _finite(value.item())
    return None


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if isinstance(value, int) or math.isfinite(value) else None


def _json(content: Any, status: int = 200) -> Response:
    body = json.dumps(_finite(content), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return Response(body, status_code=status, media_type="application/json",
                    headers={"Cache-Control": "no-store"})


def _error(status: int, code: str, message: str) -> Response:
    return _json({"error": {"code": code, "message": message}}, status)


def _park_of(url: str | None) -> str | None:
    official = official_source_url(url)
    return official.split("/")[3] if official else None


# --------------------------------------------------------------------------
# Request schema
# --------------------------------------------------------------------------

def _clean_text(value: str, limit: int) -> str:
    if _CONTROL.search(value):
        raise ValueError("control characters are not allowed")
    if not value.strip():
        raise ValueError("must not be blank")
    if len(value) > limit:
        raise ValueError(f"must be at most {limit} characters")
    return value


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def bounded(cls, value: str) -> str:
        return _clean_text(value, MAX_HISTORY_CONTENT_CHARS)


class ChatRequest(BaseModel):
    """Only these three fields. Retrieval/generation settings are not accepted."""
    model_config = ConfigDict(extra="forbid", strict=True)
    selected_park: Literal["yose", "yell", "grca"]
    question: str
    history: list[HistoryMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)

    @field_validator("question")
    @classmethod
    def bounded(cls, value: str) -> str:
        return _clean_text(value, MAX_QUESTION_CHARS).strip()

    @model_validator(mode="after")
    def alternating(self) -> "ChatRequest":
        roles = [message.role for message in self.history]
        if len(roles) % 2 or any(role != ("user" if index % 2 == 0 else "assistant") for index, role in enumerate(roles)):
            raise ValueError("history must alternate user/assistant pairs")
        return self


# --------------------------------------------------------------------------
# Index metadata
# --------------------------------------------------------------------------

def _builds(connection) -> list[dict]:
    counts = {row["build_id"]: row["n"] for row in connection.execute("SELECT build_id, count(*) AS n FROM chunks GROUP BY build_id")}
    vectors = {row["build_id"]: row["n"] for row in connection.execute("SELECT build_id, count(*) AS n FROM embeddings GROUP BY build_id")}
    builds = []
    for row in connection.execute("SELECT build_id, active, manifest_json FROM index_builds ORDER BY active DESC, build_id"):
        manifest = json.loads(row["manifest_json"])
        embedding = manifest.get("identity", {}).get("embedding", {})
        chunker = manifest.get("identity", {}).get("chunker", {})
        builds.append({
            "build_id": row["build_id"], "active": bool(row["active"]),
            "strategy": manifest.get("strategy"), "created_at": manifest.get("created_at"),
            "chunk_count": counts.get(row["build_id"], 0), "vector_count": vectors.get(row["build_id"], 0),
            "dimension": _number(manifest.get("dimension")),
            "embedding_deployment": embedding.get("deployment"),
            "target_tokens": _number(chunker.get("target")), "overlap_tokens": _number(chunker.get("overlap")),
        })
    return builds


def active_structure_build() -> dict:
    """The web app answers only from the active structure-aware build."""
    with _connect() as connection:
        active = [build for build in _builds(connection) if build["active"]]
    if not active:
        raise WebError(503, "index_missing", "No active index build is available.")
    build = active[0]
    if build["strategy"] != "structure":
        raise WebError(503, "index_not_structure", "The active index is not the structure-aware build used by the web app.")
    if not build["chunk_count"] or build["chunk_count"] != build["vector_count"]:
        raise WebError(503, "index_incomplete", "The active index has missing vectors.")
    return build


def metadata() -> dict:
    settings = config()
    with _connect() as connection:
        builds = _builds(connection)
        active = next((build for build in builds if build["active"]), None)
        docs = connection.execute(
            "SELECT doc_id, source_url, page_type, crawled_at, json_extract(normalized_blocks_json, '$.has_table') AS has_table FROM documents").fetchall()
        active_chunks = {}
        if active:
            for row in connection.execute("SELECT doc_id, count(*) AS n FROM chunks WHERE build_id=? GROUP BY doc_id", (active["build_id"],)):
                active_chunks[row["doc_id"]] = row["n"]
    parks = []
    for code in PARK_CODES:
        rows = [row for row in docs if _park_of(row["source_url"]) == code]
        captured = sorted(row["crawled_at"] for row in rows if row["crawled_at"])
        parks.append({
            "code": code, "name": core.PARK_NAMES[code], "documents": len(rows),
            "html": sum(row["page_type"] == "html" for row in rows),
            "pdf": sum(row["page_type"] == "pdf" for row in rows),
            "table_documents": sum(bool(row["has_table"]) for row in rows),
            "active_chunks": sum(active_chunks.get(row["doc_id"], 0) for row in rows),
            "captured_earliest": captured[0] if captured else None,
            "captured_latest": captured[-1] if captured else None,
        })
    ready = core.gold_drafts_ready()
    runtime = runtime_profile()
    if hosted():
        persistence = {
            "conversation_text": "browser tab memory only; sent to this server per request and not stored by it",
            "embedding_cache": "/tmp/parkguide/embedding-cache/ on this instance only (ephemeral): SHA-256 of each embedded retrieval query, its vector and metadata (no query text)",
            "budget_ledger": "/tmp/parkguide/api-ledger.json on this instance only (ephemeral, not shared across instances): kind, time, status, tokens and estimated cost of each paid call (no text)",
        }
    else:
        persistence = {
            "conversation_text": "browser tab memory only; sent to this server per request and not stored by it",
            "embedding_cache": "data/embedding-cache/: SHA-256 of each embedded retrieval query, its vector and metadata (no query text)",
            "budget_ledger": "artifacts/api-ledger.json: kind, time, status, tokens and estimated cost of each paid call (no text)",
        }
    return {
        "parks": parks,
        "totals": {
            "documents": len(docs), "html": sum(row["page_type"] == "html" for row in docs),
            "pdf": sum(row["page_type"] == "pdf" for row in docs),
            "table_documents": sum(bool(row["has_table"]) for row in docs),
            "chunks_all_builds": sum(build["chunk_count"] for build in builds),
            "vectors_all_builds": sum(build["vector_count"] for build in builds),
        },
        "active_build": active, "builds": builds,
        "models": {
            "embedding": {"deployment": settings["embedding"]["deployment"], "dimension": settings["embedding"]["dimension"]},
            "generation": {"model": settings["generation"]["model"], "deployment": settings["generation"]["deployment"]},
            "reranker": {"model": settings["retrieval"]["reranker"], "revision": settings["retrieval"]["reranker_revision"],
                         "enabled": runtime["rerank_enabled"]},
            # The one approved resource for both deployments (no credential).
            "azure_resource": {"endpoint": settings["embedding"]["endpoint"],
                               "embedding_deployment": settings["embedding"]["deployment"],
                               "generation_deployment": settings["generation"]["deployment"],
                               "generation_store_requested": False},
        },
        "local_persistence": persistence,
        "runtime": runtime,
        "retrieval": {
            "mode": "hybrid", "strategy": "structure",
            "candidate_count": settings["retrieval"]["candidate_count"],
            "final_context_count": settings["retrieval"]["final_context_count"],
            "rrf_k": settings["retrieval"]["rrf_k"],
            "selected_park_rerank": runtime["rerank_enabled"],
            "context_token_budget": settings["retrieval"]["context_token_budget"],
        },
        "chat": {"ready": ready, "reason": None if ready else "gold_drafts_not_frozen"},
        "history_storage": "browser_memory_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_documents(park, q, page_type, has_table, offset, limit) -> dict:
    # Every value is a bound parameter; only these fixed clause strings are SQL.
    clauses, params = [], []
    if park:
        clauses.append("d.source_url LIKE ?")
        # Same official visitor-path rule as metadata counts (_park_of).
        params.append(f"https://www.nps.gov/{park}/planyourvisit/%")
    if q:
        clauses.append("(d.title LIKE ? ESCAPE '\\' OR d.source_url LIKE ? ESCAPE '\\')")
        params += [_like(q), _like(q)]
    if page_type:
        clauses.append("d.page_type = ?")
        params.append(page_type)
    if has_table is not None:
        clauses.append("coalesce(json_extract(d.normalized_blocks_json, '$.has_table'), 0) = ?")
        params.append(1 if has_table else 0)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as connection:
        active = connection.execute("SELECT build_id FROM index_builds WHERE active=1").fetchone()
        total = connection.execute(f"SELECT count(*) FROM documents d{where}", params).fetchone()[0]
        rows = connection.execute(
            "SELECT d.doc_id, d.source_url, d.title, d.page_type, d.effective_date, d.crawled_at, "
            "json_extract(d.normalized_blocks_json, '$.has_table') AS has_table, "
            "(SELECT count(*) FROM chunks c WHERE c.doc_id=d.doc_id AND c.build_id=?) AS active_chunks "
            f"FROM documents d{where} ORDER BY d.title, d.doc_id LIMIT ? OFFSET ?",
            [active["build_id"] if active else "", *params, limit, offset]).fetchall()
    items = []
    for row in rows:
        url = official_source_url(row["source_url"])
        items.append({
            "doc_id": row["doc_id"], "title": row["title"], "source_url": url, "park": _park_of(url),
            "page_type": row["page_type"], "has_table": bool(row["has_table"]),
            "effective_date": row["effective_date"], "crawled_at": row["crawled_at"],
            "captured_label": captured_label(row["crawled_at"]), "active_chunks": row["active_chunks"],
        })
    return {"total": total, "offset": offset, "limit": limit, "items": items}


def document_detail(doc_id: str, block_offset: int, block_limit: int) -> dict:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        if not row:
            raise WebError(404, "document_not_found", "No stored document has that identifier.")
        builds = _builds(connection)
        per_build = {r["build_id"]: r["n"] for r in connection.execute(
            "SELECT build_id, count(*) AS n FROM chunks WHERE doc_id=? GROUP BY build_id", (doc_id,))}
    bundle = json.loads(row["normalized_blocks_json"])
    blocks = bundle.get("blocks", []) if isinstance(bundle, dict) else []
    sections = []
    for index, block in enumerate(blocks[block_offset:block_offset + block_limit], start=block_offset):
        text = block.get("text", "") if isinstance(block, dict) else ""
        sections.append({
            "index": index, "heading_path": block.get("heading_path", ""), "kind": block.get("kind", "paragraph"),
            "start": _number(block.get("start")), "end": _number(block.get("end")),
            "text": text[:4000], "truncated": len(text) > 4000,
        })
    url = official_source_url(row["source_url"])
    return {
        "doc_id": row["doc_id"], "title": row["title"], "source_url": url, "park": _park_of(url),
        "page_type": row["page_type"], "effective_date": row["effective_date"], "crawled_at": row["crawled_at"],
        "captured_label": captured_label(row["crawled_at"]), "content_hash": row["content_hash"],
        "has_table": bool(bundle.get("has_table")) if isinstance(bundle, dict) else False,
        "block_count": len(blocks), "block_offset": block_offset, "block_limit": block_limit, "sections": sections,
        "chunks_by_build": [{"build_id": build["build_id"], "strategy": build["strategy"], "active": build["active"],
                             "chunks": per_build.get(build["build_id"], 0)} for build in builds],
    }


def document_passages(doc_id: str, offset: int, limit: int) -> dict:
    with _connect() as connection:
        if not connection.execute("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)).fetchone():
            raise WebError(404, "document_not_found", "No stored document has that identifier.")
        active = connection.execute("SELECT build_id FROM index_builds WHERE active=1").fetchone()
        if not active:
            raise WebError(503, "index_missing", "No active index build is available.")
        total = connection.execute("SELECT count(*) FROM chunks WHERE build_id=? AND doc_id=?", (active[0], doc_id)).fetchone()[0]
        # Document order is applied before LIMIT/OFFSET, so every page is a
        # contiguous slice: first span start, then last span start (table
        # chunks repeat their header span), then chunk ID as a stable tiebreak.
        rows = connection.execute(
            "SELECT chunk_id, heading_path, text, token_count, source_span_json FROM chunks WHERE build_id=? AND doc_id=? "
            "ORDER BY json_extract(source_span_json, '$[0].start'), json_extract(source_span_json, '$[#-1].start'), chunk_id "
            "LIMIT ? OFFSET ?", (active[0], doc_id, limit, offset)).fetchall()
    passages = []
    for position, row in enumerate(rows, start=offset + 1):
        spans = json.loads(row["source_span_json"])
        passages.append({
            "position": position, "chunk_id": row["chunk_id"], "heading_path": row["heading_path"], "text": row["text"],
            "token_count": row["token_count"], "source_spans": _spans(spans),
        })
    return {"build_id": active[0], "strategy_note": "active build only", "total": total, "offset": offset, "limit": limit, "passages": passages}


def _spans(spans: Any) -> list[dict]:
    clean = []
    for span in spans if isinstance(spans, list) else []:
        if isinstance(span, dict) and isinstance(span.get("start"), int) and isinstance(span.get("end"), int):
            clean.append({"start": span["start"], "end": span["end"], "kind": str(span.get("kind", ""))[:40]})
    return clean


# --------------------------------------------------------------------------
# Chat turn
# --------------------------------------------------------------------------

def _observed_embedder(observation: dict):
    """Delegate to the shared embedding_cache.cached_embed and note what was seen.

    Only two facts are recorded here: whether this process saw the cache files
    for the query hash just before the call (a file-presence observation that
    another process could change), and the call's wall time. Whether Azure was
    contacted is decided afterwards from the ledger window, not from this check.
    """
    def embed(texts):
        folder = embedding_cache.cache_folder()
        keys = [hashlib.sha256(text.encode()).hexdigest() for text in texts]
        present = all((folder / f"{key}.npy").exists() and (folder / f"{key}.json").exists() for key in keys)
        observation.update(called=True, query_sha256=keys[0] if len(keys) == 1 else None,
                           cache_file_present_before_call=present)
        started = time.perf_counter()
        try:
            return embedding_cache.cached_embed(texts)
        finally:
            observation["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return embed


def _ledger_events() -> list[dict] | None:
    """Read the shared budget ledger under a shared lock; never writes it."""
    path = ledger_path()
    lock_path = path.with_suffix(".lock")
    try:
        if not path.exists():
            return []
        if lock_path.exists():
            with lock_path.open("r") as lock:
                fcntl.flock(lock, fcntl.LOCK_SH)
                ledger = json.loads(path.read_text())
        else:
            ledger = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    events = ledger.get("events") if isinstance(ledger, dict) else None
    return [event for event in events if isinstance(event, dict)] if isinstance(events, list) else None


_LEDGER_STATUS = {"reported_usage": "reported_usage", "provider_error_reserved": "failed_attempts", "reserved": "unsettled_reservations"}


def ledger_window(before: list[dict] | None, after: list[dict] | None) -> dict:
    """Summarize ledger events added while this request held the answer lock.

    Includes embedding calls, failed attempts and retries. Missing token usage
    is counted as missing, never as zero; failed calls without reported usage
    keep their conservative reservation as the cost estimate.
    """
    if before is None or after is None:
        return {"captured": False, "reason": "The local budget ledger could not be read."}
    seen = {event.get("id") for event in before}
    new = [event for event in after if event.get("id") not in seen]
    kinds: dict[str, dict] = {}
    total = 0.0
    reserved_maximums = False
    for event in new:
        kind = event.get("kind") if event.get("kind") in ("embedding", "generation") else "other"
        bucket = kinds.setdefault(kind, {"events": 0, "reported_usage": 0, "failed_attempts": 0, "unsettled_reservations": 0,
                                         "input_tokens": None, "output_tokens": None, "events_without_token_usage": 0,
                                         "cost_estimate_usd": 0.0})
        bucket["events"] += 1
        status = _LEDGER_STATUS.get(event.get("status"))
        if status:
            bucket[status] += 1
        tokens_in, tokens_out = event.get("input_tokens"), event.get("output_tokens")
        if isinstance(tokens_in, int) and not isinstance(tokens_in, bool):
            bucket["input_tokens"] = (bucket["input_tokens"] or 0) + tokens_in
            if isinstance(tokens_out, int) and not isinstance(tokens_out, bool):
                bucket["output_tokens"] = (bucket["output_tokens"] or 0) + tokens_out
        else:
            bucket["events_without_token_usage"] += 1
            reserved_maximums = True
        cost = _number(event.get("cost_estimate_usd"))
        if cost is not None:
            bucket["cost_estimate_usd"] += cost
            total += cost
    return {
        "captured": True, "events": len(new), "cost_estimate_usd": total if new else 0.0, "by_kind": kinds,
        "includes_reserved_maximums": reserved_maximums,
        "basis": "Estimated from published prices and provider-reported tokens in the local budget ledger; not an invoice. "
                 "Kind 'generation' covers both answer drafting and claim review calls.",
        "limitation": "The window is every ledger event added while this request held the answer lock. A CLI or legacy "
                      "Streamlit process spending at the same time would also appear here. On Vercel the ledger is "
                      "per instance and ephemeral.",
    }


def _embedding_status(observation: dict, window: dict) -> dict:
    """Prefer ledger evidence for a network call; label file observations as such."""
    if not observation.get("called"):
        status = "not_requested"
    elif not window.get("captured"):
        status = "not_captured"
    else:
        bucket = window["by_kind"].get("embedding")
        if bucket and bucket["reported_usage"]:
            status = "azure_request_recorded"
        elif bucket:
            status = "azure_attempt_failed_recorded"
        else:
            status = "no_azure_request_recorded"
    return {
        "status": status, "elapsed_ms": _number(observation.get("elapsed_ms")),
        "query_sha256": observation.get("query_sha256"),
        "cache_file_present_before_call": observation.get("cache_file_present_before_call"),
        "deployment": config()["embedding"]["deployment"],
    }


def _stored_passages(build_id: str, chunk_ids: list[str]) -> dict:
    if not chunk_ids:
        return {}
    marks = ",".join("?" for _ in chunk_ids)
    with _connect() as connection:
        rows = connection.execute(
            f"SELECT c.chunk_id, c.doc_id, c.text, d.content_hash, d.source_url FROM chunks c JOIN documents d USING(doc_id) "
            f"WHERE c.build_id=? AND c.chunk_id IN ({marks})", [build_id, *chunk_ids]).fetchall()
    return {row["chunk_id"]: dict(row) for row in rows}


def _safe_message(value: Any) -> str | None:
    return value if isinstance(value, str) and _SAFE_MESSAGE.match(value) else None


def _review_summary(review: Any) -> dict:
    """Public AI review metadata for the one successful review call, if any.

    Rejected decisions contribute only a count: their reasons can describe the
    withheld draft claim. Review failures expose only safe codes.
    """
    if not isinstance(review, dict):
        return {"status": "not_run"}
    usage = review.get("usage") if isinstance(review.get("usage"), dict) else {}
    summary = {
        "status": "passed", "model": review.get("model") if isinstance(review.get("model"), str) else None,
        "input_tokens": _number(usage.get("input_tokens")), "output_tokens": _number(usage.get("output_tokens")),
        "elapsed_ms": _number(review.get("elapsed_ms")), "cost_estimate_usd": _number(review.get("cost_estimate_usd")),
        "withheld_claims": _number(review.get("withheld_claims")),
    }
    if isinstance(review.get("error"), dict):
        error = review["error"]
        diagnostics = error.get("diagnostics") if isinstance(error.get("diagnostics"), dict) else {}
        reason = diagnostics.get("validation_reason")
        summary.update(status="error", error_type=_safe_message(error.get("type")),
                       error_message=_safe_message(error.get("message")),
                       validation_reason=reason if isinstance(reason, str) and _SAFE_CODE.match(reason) else None,
                       input_tokens=None, output_tokens=None, elapsed_ms=None, cost_estimate_usd=None, model=None)
        return summary
    decisions = review.get("decisions") if isinstance(review.get("decisions"), list) else []
    if summary["withheld_claims"]:
        supported = sum(1 for decision in decisions if isinstance(decision, dict) and decision.get("supported") is True)
        summary["status"] = "partially_withheld" if supported else "all_withheld"
    return summary


def _review_judgments(review: Any, claims: list, stored: dict) -> tuple[list[dict], list[str]]:
    """Map supported decisions onto retained delivered claims, failing closed.

    The core retains claims in claim_index order of supported decisions, so the
    k-th delivered claim belongs to the k-th supported decision. Every witness
    must cite one of that claim's own evidence IDs and occur verbatim in the
    stored passage, and every cited passage must have a witness.
    """
    if not isinstance(review, dict) or isinstance(review.get("error"), dict) or not isinstance(review.get("decisions"), list):
        return [], ["review_missing_for_delivered_answer"]
    supported = [decision for decision in review["decisions"] if isinstance(decision, dict) and decision.get("supported") is True]
    if any(type(decision.get("claim_index")) is not int for decision in supported):
        return [], ["invalid_review_decision_index"]
    supported.sort(key=lambda decision: decision["claim_index"])
    if len(supported) != len(claims):
        return [], ["review_decision_count_mismatch"]
    errors, judgments = set(), []
    for claim, decision in zip(claims, supported):
        cited = set(claim.get("evidence_ids", []))
        quotes = decision.get("supporting_quotes")
        witnessed, witnesses = set(), []
        for quote in quotes if isinstance(quotes, list) else []:
            if (not isinstance(quote, dict) or not isinstance(quote.get("evidence_id"), str)
                    or not isinstance(quote.get("quote"), str) or not quote["quote"].strip()):
                errors.add("invalid_review_witness")
            elif quote["evidence_id"] not in cited:
                errors.add("witness_outside_claim_evidence")
            elif quote["quote"] not in (stored.get(quote["evidence_id"]) or {}).get("text", ""):
                errors.add("witness_not_in_stored_passage")
            else:
                witnessed.add(quote["evidence_id"])
                witnesses.append({"evidence_id": quote["evidence_id"], "quote": quote["quote"]})
        if witnessed != cited:
            errors.add("cited_passage_without_witness")
        judgments.append({"reason": decision.get("reason") if isinstance(decision.get("reason"), str) else None,
                          "witnesses": witnesses})
    return judgments, sorted(errors)


def _reason(code: str, category: str, detail: str) -> dict:
    return {"code": code, "category": category, "detail": detail}


def _refusal_reason(result: dict, review_summary: dict, stale: bool, integrity_errors: list[str]) -> dict | None:
    """Why no reviewed answer was delivered, by the stage that stopped it.

    Categories: local_preflight (before any embedding, search or model call),
    scope_check (after local search, before any model call), validation_failure
    (local checks rejected model output or its evidence), review_failure (the
    AI review call did not complete validly), review_rejected (the review
    rejected every claim), no_evidence, model_refusal, model_clarification.
    """
    response = result["response"]
    if response.get("action") == "answer" and not stale and not integrity_errors:
        return None
    guard_errors = [code for code in result.get("guard_errors", []) if isinstance(code, str) and _SAFE_CODE.match(code)]
    if stale:
        return _reason("stale_or_unverified_source", "validation_failure",
                       "A cited passage did not match the stored active index (text, document, content hash, URL or park), so the answer was withheld.")
    if integrity_errors:
        return _reason("review_integrity_failed", "validation_failure",
                       "The source review result did not match the delivered claims and stored passages, so the answer was withheld.")
    if "selected_park_source_scope_violation" in guard_errors or response.get("preflight_reason") == "invalid_selected_park_sources":
        return _reason("selected_park_source_scope_violation", "scope_check",
                       "Local search returned evidence outside the selected park, so no answer model call was made.")
    if response.get("preflight_reason"):
        return _reason(response["preflight_reason"], "local_preflight",
                       "Stopped by a local check before any embedding, search or model call.")
    error = response.get("generation_error")
    if isinstance(error, dict) and isinstance(error.get("code"), str) and _SAFE_CODE.match(error["code"]):
        return _reason(error["code"], "validation_failure",
                       "The answer model replied, but its output failed local schema or citation validation.")
    if review_summary.get("status") == "error":
        return _reason("source_review_failed", "review_failure",
                       "The AI source review did not complete validly, so no claim was delivered.")
    if review_summary.get("status") == "all_withheld":
        return _reason("all_claims_withheld", "review_rejected", "The AI source review rejected every drafted claim.")
    if guard_errors:
        return _reason("guard_failed", "validation_failure",
                       "Local citation, number or quotation checks rejected the reviewed draft, so it was withheld.")
    if not result.get("contexts"):
        return _reason("no_saved_evidence", "no_evidence",
                       "No saved passages for this park were selected, so no answer model call was made.")
    if response.get("action") == "clarify":
        return _reason("model_requested_clarification", "model_clarification",
                       "The answer model asked for clarification instead of answering.")
    return _reason("model_refused", "model_refusal", "The answer model declined to answer from the selected passages.")


def _derivation(trace: Any, carded: set[str]) -> dict | None:
    """Safe, bounded view of a table-cell calculation behind a delivered claim."""
    if not isinstance(trace, dict):
        return None

    def text(value, limit=200):
        return value[:limit] if isinstance(value, str) else None

    operands = []
    for operand in trace.get("operands", [])[:4] if isinstance(trace.get("operands"), list) else []:
        if isinstance(operand, dict) and operand.get("chunk_id") in carded:
            operands.append({"row_label": text(operand.get("row_label")), "source_cell": text(operand.get("source_cell")),
                             "value": text(operand.get("value"), 40), "chunk_id": operand["chunk_id"],
                             "source_spans": _spans(operand.get("source_spans"))})
    if not operands:
        return None
    return {"operation": text(trace.get("operation"), 40), "column": text(trace.get("column")), "unit": text(trace.get("unit"), 40),
            "result": text(trace.get("result"), 40), "equation": text(trace.get("equation")), "operands": operands,
            "note": "Computed locally from the cited table cells; the calculated claim then went through the same source review."}


def _turn_runtime() -> dict:
    runtime = runtime_profile()
    return {key: runtime[key] for key in ("profile", "rerank_enabled", "rerank_reason", "evaluation_note")} | {
        "budget_scope": runtime["budget"]["scope"]}


def public_turn(result: dict, *, build: dict, window: dict, embedding: dict, selected_park: str,
                history_received: int, answer_call_ms: float) -> dict:
    response = result["response"]
    action = response.get("action")
    pages = cited_source_pages(result) if action == "answer" else []
    # Validate every cited passage against the stored active build and park.
    # A missing hash or identity field is a failure, not a skipped check.
    cited_ids = [passage["chunk_id"] for page in pages for passage in page["passages"]]
    stored = _stored_passages(build["build_id"], cited_ids)
    carded = set(cited_ids)

    def mismatched(page, passage):
        row = stored.get(passage["chunk_id"])
        return (row is None or not isinstance(passage.get("content_hash"), str) or not passage["content_hash"]
                or row["text"] != passage["text"] or row["doc_id"] != passage["doc_id"]
                or row["content_hash"] != passage["content_hash"]
                or _park_of(page["source_url"]) != selected_park
                or official_source_url(row["source_url"]) != page["source_url"])

    stale = action == "answer" and (not pages or any(
        identifier not in carded for claim in response.get("claims", []) for identifier in claim.get("evidence_ids", [])) or any(
        mismatched(page, passage) for page in pages for passage in page["passages"]))
    review_summary = _review_summary(result.get("citation_review"))
    judgments, integrity_errors = ([], [])
    if action == "answer" and not stale:
        judgments, integrity_errors = _review_judgments(result.get("citation_review"), response.get("claims", []), stored)
    delivered = action == "answer" and not stale and not integrity_errors
    claims = response.get("claims", []) if delivered else []
    if not delivered:
        judgments = []
    witnesses_by_claim = {index: judgment["witnesses"] for index, judgment in enumerate(judgments, 1)}
    sources = []
    if delivered:
        for number, page in enumerate(pages, 1):
            passages = []
            for passage in page["passages"]:
                passages.append({
                    "chunk_id": passage["chunk_id"], "doc_id": passage["doc_id"],
                    "heading_path": passage["heading_path"], "excerpt": passage["excerpt"],
                    "excerpt_leading_omission": passage["excerpt_leading_omission"],
                    "excerpt_truncated": passage["excerpt_truncated"],
                    "saved_text": passage["text"], "pdf_start_page": passage["pdf_start_page"],
                    "passage_url": passage["passage_url"], "source_spans": _spans(passage["source_spans"]),
                    "claim_numbers": passage["claim_numbers"],
                    "reviewer_witnesses": [{"claim_number": claim, "quote": witness["quote"]}
                                           for claim in passage["claim_numbers"]
                                           for witness in witnesses_by_claim.get(claim, [])
                                           if witness["evidence_id"] == passage["chunk_id"]],
                })
            sources.append({
                "number": number, "title": page["title"], "source_url": page["source_url"],
                "park": _park_of(page["source_url"]), "page_type": page["page_type"],
                "effective_date": page["effective_date"], "crawled_at": page["crawled_at"],
                "captured_label": page["captured_label"], "passages": passages,
            })
    page_numbers = {passage["chunk_id"]: source["number"] for source in sources for passage in source["passages"]}
    public_claims = [{
        "number": index, "text": claim["text"],
        "source_numbers": sorted({page_numbers[identifier] for identifier in claim["evidence_ids"] if identifier in page_numbers}),
        "review": {"reason": judgments[index - 1]["reason"]},
    } for index, claim in enumerate(claims, 1)]
    if delivered:
        status, text = "answer", " ".join(claim["text"] for claim in claims)
    elif action == "clarify":
        status, text = "clarification", response.get("answer", "")
    else:
        status = "refusal"
        text = ("I could not confirm the cited passages against the stored index, so the answer was withheld. Please check the official NPS information."
                if stale else
                "I could not confirm that the source review matched this answer, so it was withheld. Please check the official NPS information."
                if action == "answer" and integrity_errors else response.get("answer", ""))
    trace = result.get("retrieval") or {}
    context_ids = [item["chunk_id"] for item in result.get("contexts", [])]
    cited_set = set(page_numbers)
    candidates = []
    pre = {item.get("chunk_id"): item.get("pre_rank") for item in trace.get("candidates", [])}
    # Show the ranked list, plus any candidate/final entry missing from it, so
    # an unexpected (for example out-of-park) passage is visible, not hidden.
    listed, ordered = set(), []
    for item in [*(trace.get("reranked") or trace.get("candidates", [])), *trace.get("candidates", []), *trace.get("final", [])]:
        if isinstance(item, dict) and item.get("chunk_id") not in listed:
            listed.add(item.get("chunk_id"))
            ordered.append(item)
    for item in ordered:
        scores = item.get("scores", {}) if isinstance(item.get("scores"), dict) else {}
        url = official_source_url(item.get("source_url"))
        candidates.append({
            "chunk_id": item.get("chunk_id"), "doc_id": item.get("doc_id"), "title": item.get("title"),
            "heading_path": item.get("heading_path"), "source_url": url, "page_type": item.get("page_type"),
            "park": _park_of(url), "in_selected_park": _park_of(url) == selected_park,
            "pre_rank": _number(pre.get(item.get("chunk_id"), item.get("pre_rank"))),
            "post_rank": _number(item.get("post_rank", item.get("rank"))),
            "scores": {name: _number(scores.get(name)) for name in ("dense", "bm25", "rrf", "rerank")},
            "retriever_ranks": {name: _number(value) for name, value in (item.get("retriever_ranks") or {}).items() if name in ("dense", "bm25")},
            "in_context": item.get("chunk_id") in context_ids, "cited": item.get("chunk_id") in cited_set,
            "snippet": (item.get("text") or "")[:360],
        })
    timings = trace.get("timings", {}) if isinstance(trace.get("timings"), dict) else {}
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    total_cost = _number(response.get("cost_estimate_usd"))
    review_cost = review_summary.get("cost_estimate_usd")
    filters = result.get("filters") or {}
    selection = trace.get("context_selection") if isinstance(trace.get("context_selection"), dict) else None
    retrieval_ran = bool(trace.get("candidates")) or "eligible_count" in trace
    generation_ran = bool(usage) or bool(response.get("generation_error"))
    rerank_ran = retrieval_ran and bool(result.get("rerank_enabled"))
    history_used = result.get("history") if isinstance(result.get("history"), list) else []
    return {
        "turn_id": uuid.uuid4().hex,
        "selected_park": selected_park,
        "question": result["question"],
        "status": status,
        "text": text,
        "claims": public_claims,
        "sources": sources,
        # Sent back by the browser as the assistant turn; never used as evidence.
        "history_content": result.get("rendered", "") if delivered else text,
        "history_scope_reset": bool(result.get("history_scope_reset")),
        "runtime": _turn_runtime(),
        "reason": _refusal_reason(result, review_summary, stale, integrity_errors),
        # Nested wall times: server_ms (whole handler, set by run_chat) contains
        # answer_call_ms (the shared answer() call, measured here), which
        # contains pipeline_ms (answer()'s own measurement, including retry
        # waits and any first-use reranker load).
        "timing": {"answer_call_ms": round(answer_call_ms, 1), "pipeline_ms": _number(result.get("elapsed_ms")), "server_ms": None},
        "history": {"messages_received": history_received, "messages_used": len(history_used),
                    "scope_reset": bool(result.get("history_scope_reset"))},
        "inspector": {
            "retrieval": {
                "ran": retrieval_ran,
                "query": result.get("retrieval_query") if retrieval_ran else None,
                "keyword_query": trace.get("keyword_query") if retrieval_ran else None,
                "keyword_current_terms": trace.get("keyword_current_terms") if retrieval_ran else None,
                "keyword_candidate_count": trace.get("keyword_candidate_count") if retrieval_ran else None,
                "filters": {"parks": [park for park in filters.get("parks", []) if park in PARK_CODES],
                            "source_url_count": len(filters.get("source_url", [])) if isinstance(filters.get("source_url"), list) else 0},
                "mode": trace.get("mode"), "build_id": trace.get("build_id"), "build_strategy": build["strategy"],
                "rerank_enabled": bool(result.get("rerank_enabled")),
                "eligible_count": _number(trace.get("eligible_count")),
                "candidate_count": _number(trace.get("candidate_count")),
                "requested_candidates": _number(trace.get("requested_candidates")),
                "final_count": len(trace.get("final", [])), "context_count": len(context_ids),
                "shortfall": trace.get("shortfall") if isinstance(trace.get("shortfall"), bool) else None,
                # total_ms contains load_ms, retrieval_ms and rerank_ms; it
                # excludes query embedding, which happens before retrieval.
                "timings_ms": {"load_ms": _number(timings.get("load_ms")), "retrieval_ms": _number(timings.get("retrieval_ms")),
                               "rerank_ms": _number(timings.get("rerank_ms")) if rerank_ran else None,
                               "total_ms": _number(timings.get("total_ms"))},
                "score_labels": SCORE_LABELS,
                "candidates": candidates,
                "context_ids": context_ids,
                "context_selection": {"method": selection.get("method"), "selected_ids": selection.get("selected_ids")} if selection else None,
            },
            "embedding": embedding,
            # Metrics of the final, successful answer call as reported by the
            # shared path. Failed attempts and retries appear only in the
            # ledger window below.
            "generation": {
                "ran": generation_ran,
                "returned_model": response.get("model") if isinstance(response.get("model"), str) else None,
                "requested_deployment": response.get("requested_model") if isinstance(response.get("requested_model"), str) else None,
                "input_tokens": _number(usage.get("input_tokens")) if generation_ran else None,
                "output_tokens": _number(usage.get("output_tokens")) if generation_ran else None,
                "elapsed_ms": _number(response.get("elapsed_ms")) if generation_ran else None,
                # The shared path adds review cost to the payload only after a
                # completed review; otherwise the payload holds generation alone.
                "cost_estimate_usd": None if not generation_ran else
                                     (total_cost - review_cost) if total_cost is not None and review_cost is not None
                                     else (total_cost if review_summary["status"] in ("not_run", "error") else None),
            },
            "review": review_summary,
            "ledger_window": window,
            "guard_errors": [code for code in result.get("guard_errors", []) if isinstance(code, str) and _SAFE_CODE.match(code)],
            "integrity_errors": integrity_errors,
            "derivation": _derivation(result.get("source_derivation"), carded) if delivered else None,
            "config_hash": result.get("config_hash"),
            "timestamp": result.get("timestamp"),
        },
    }


def run_chat(request: ChatRequest) -> dict:
    if not core.gold_drafts_ready():
        raise WebError(503, "chat_unavailable", "Chat is disabled until the 40 source-based gold drafts are frozen.")
    build = active_structure_build()
    started = time.perf_counter()
    if not _ANSWER_LOCK.acquire(blocking=False):
        raise WebError(409, "busy", "Another question is still being processed by this server (possibly one you stopped "
                       "waiting for; stopping in the browser does not stop the server). Try again shortly.")
    observation: dict = {}
    failure: Exception | None = None
    result = None
    try:
        before = _ledger_events()
        call_started = time.perf_counter()
        # Hosted forces rerank=False; locally the shared path's config default applies.
        override = rerank_override()
        try:
            result = core.answer(
                request.question, [message.model_dump() for message in request.history],
                mode="hybrid", build_id=build["build_id"], selected_park=request.selected_park,
                embedder=_observed_embedder(observation), **({} if override is None else {"rerank": override}),
            )
        except Exception as error:  # Never return arbitrary exception text.
            failure = error
        answer_call_ms = (time.perf_counter() - call_started) * 1000
        # Read the window while still holding the lock so this process cannot
        # add another request's events to it.
        window = ledger_window(before, _ledger_events())
    finally:
        _ANSWER_LOCK.release()
    embedding = _embedding_status(observation, window)
    if failure is not None:
        log.warning("chat request failed: %s", type(failure).__name__)
        error = _classify(failure)
        error.details = {"ledger_window": window, "embedding": embedding, "answer_call_ms": round(answer_call_ms, 1),
                         "runtime": _turn_runtime()}
        raise error from None
    turn = public_turn(result, build=build, window=window, embedding=embedding, selected_park=request.selected_park,
                       history_received=len(request.history), answer_call_ms=answer_call_ms)
    turn["timing"]["server_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return turn


# GenerationError codes raised by configuration checks before any generation
# request is sent (generation.Generator.__init__/_configuration).
_GENERATION_CONFIG_CODES = {
    "invalid_provider_or_model", "missing_approved_generation_deployment", "invalid_accepted_response_models",
    "invalid_frozen_generation_settings", "generation_endpoint_differs_from_embedding_resource",
    "separate_generation_configuration_not_supported", "azure_configuration_differs_from_approved",
    "azure_generation_requires_approved_dev_endpoint", "missing_generation_credential",
}
_EARLIER = " Earlier stages of this request may already have made recorded calls; see the ledger window."


def _classify(error: Exception) -> WebError:
    """Fixed codes and wording; never the exception text. Browser aborts do not apply here."""
    from .generation import GenerationError
    message = str(error)
    if isinstance(error, GenerationError):
        code = error.code if isinstance(error.code, str) and _SAFE_CODE.match(error.code) else "generation_error"
        if code in _GENERATION_CONFIG_CODES:
            return WebError(503, "model_not_configured",
                            f"The answer-model configuration check failed ({code}) before a generation request was sent." + _EARLIER)
        status = f" (HTTP {error.status_code})" if isinstance(error.status_code, int) else ""
        return WebError(502, "model_request_failed", f"The Azure model request failed: {code}{status}. No answer was produced." + _EARLIER)
    if isinstance(error, RuntimeError) and message.startswith("API budget cap reached"):
        return WebError(503, "budget_exhausted",
                        ("This instance's API budget cap was reached during this request" if hosted() else
                         "The local API budget cap was reached during this request") +
                        ", so no further model request was sent." + _EARLIER)
    if isinstance(error, RuntimeError) and message.startswith("Azure embedding configuration is incomplete"):
        return WebError(503, "embedding_not_configured", "The Azure embedding settings are incomplete; no embedding request was sent.")
    if isinstance(error, RuntimeError) and message.startswith("Azure environment differs from approved configuration"):
        return WebError(503, "azure_configuration_mismatch",
                        "The Azure settings differ from the approved resource; no embedding request was sent.")
    if isinstance(error, RuntimeError) and message.startswith("Azure embedding"):
        return WebError(502, "embedding_request_failed", "The Azure embedding request failed. No answer was produced." + _EARLIER)
    if isinstance(error, RuntimeError) and message.startswith("Embedding cache integrity check failed"):
        return WebError(500, "embedding_cache_integrity_failed", "A locally cached query vector failed its integrity check.")
    if isinstance(error, RuntimeError) and "price metadata is missing" in message:
        return WebError(503, "pricing_missing", "Published price metadata is missing; paid calls are disabled." + _EARLIER)
    if isinstance(error, ValueError) and message.startswith("Reranker input would be silently truncated"):
        return WebError(422, "question_too_long_for_reranker",
                        "The retrieval query, including topics carried over from earlier turns, is too long for the local "
                        "reranker. Shorten the question or start a new conversation." + _EARLIER)
    if isinstance(error, OSError):
        return WebError(503, "local_resource_unavailable",
                        "A local model or file could not be loaded (the reranker runs offline from its local cache)." + _EARLIER)
    return WebError(500, "internal_error", "The request failed inside the local server. Details were not exposed." + _EARLIER)


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------

app = FastAPI(title="ParkGuide web app", docs_url=None, redoc_url=None, openapi_url=None)

_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; frame-src 'none'; frame-ancestors 'none'; object-src 'none'; "
        "base-uri 'none'; form-action 'self'")


@app.middleware("http")
async def local_only(request: Request, call_next):
    """Reject foreign Host (DNS rebinding) and cross-origin or non-JSON writes.

    Only the Host header is compared against the server-side allowlist;
    X-Forwarded-Host and other client-supplied forwarding headers are ignored.
    """
    hosts = _allowed_hosts()
    if request.headers.get("host", "") not in hosts:
        return _error(421, "host_not_allowed", "This server only answers requests for its configured address.")
    if request.method not in ("GET", "HEAD"):
        origin = request.headers.get("origin")
        if origin not in _allowed_origins() or (hosted() and origin != f"https://{request.headers.get('host', '')}"):
            return _error(403, "origin_not_allowed", "Cross-origin or origin-less writes are refused.")
        if request.headers.get("sec-fetch-site") not in (None, "same-origin"):
            return _error(403, "origin_not_allowed", "Cross-site writes are refused.")
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            return _error(415, "json_required", "Send application/json.")
        length = request.headers.get("content-length")
        if length is None or not length.isdigit() or int(length) > MAX_BODY_BYTES:
            return _error(413, "body_too_large", "The request body is missing a length or is too large.")
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    return response


@app.exception_handler(WebError)
async def web_error(_request: Request, error: WebError):
    body: dict = {"error": {"code": error.code, "message": error.message}}
    if error.details:
        body["error"]["details"] = error.details
    return _json(body, error.status)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, error: RequestValidationError):
    # Report field locations and error types only; never echo submitted values.
    fields = sorted({".".join(str(part) for part in item.get("loc", ()) if part != "body") for item in error.errors()})
    return _json({"error": {"code": "invalid_request", "message": "The request did not match the allowed schema.",
                            "fields": [field for field in fields if field][:20]}}, 422)


@app.exception_handler(StarletteHTTPException)
async def http_error(_request: Request, error: StarletteHTTPException):
    codes = {404: "not_found", 405: "method_not_allowed"}
    return _error(error.status_code, codes.get(error.status_code, "http_error"), "Not available.")


@app.exception_handler(Exception)
async def unexpected(_request: Request, error: Exception):
    log.warning("unexpected server error: %s", type(error).__name__)
    return _error(500, "internal_error", "The request failed inside the local server. Details were not exposed.")


@app.get("/api/health")
def health():
    return _json({"status": "ok", "dist_built": (DIST / "index.html").is_file(), "profile": runtime_profile()["profile"]})


@app.get("/api/meta")
def meta():
    return _json(metadata())


@app.get("/api/documents")
def documents(
    park: Literal["yose", "yell", "grca"] | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page_type: Literal["html", "pdf"] | None = None,
    has_table: bool | None = None,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
):
    if q is not None and _CONTROL.search(q):
        raise WebError(422, "invalid_request", "The search text contains control characters.")
    return _json(list_documents(park, (q or "").strip() or None, page_type, has_table, offset, limit))


def _doc_id(doc_id: str) -> str:
    if not _ID.match(doc_id):
        raise WebError(404, "document_not_found", "No stored document has that identifier.")
    return doc_id


@app.get("/api/documents/{doc_id}")
def document(doc_id: str, block_offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
             block_limit: Annotated[int, Query(ge=1, le=100)] = 40):
    return _json(document_detail(_doc_id(doc_id), block_offset, block_limit))


@app.get("/api/documents/{doc_id}/passages")
def passages(doc_id: str, offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
             limit: Annotated[int, Query(ge=1, le=50)] = 20):
    return _json(document_passages(_doc_id(doc_id), offset, limit))


@app.post("/api/chat")
def chat(request: ChatRequest):
    return _json(run_chat(request))


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def unknown_api(rest: str):
    return _error(404, "not_found", "Unknown API route.")


@app.get("/{path:path}")
def frontend(path: str):
    """Serve only files inside web/dist; every other path gets the SPA shell."""
    index = DIST / "index.html"
    if not index.is_file():
        return Response("ParkGuide web bundle is not built. Run: npm --prefix web ci && npm --prefix web run build",
                        status_code=503, media_type="text/plain")
    root = DIST.resolve()
    if path:
        candidate = (DIST / path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            cache = "public, max-age=31536000, immutable" if candidate.parent == root / "assets" else "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        if "." in Path(path).name:
            return _error(404, "not_found", "Not available.")
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


def main():
    import uvicorn
    # The pinned reranker must load from the local cache: no Hugging Face
    # network access from this process (Azure is the only remote service).
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host=HOST, port=PORT, proxy_headers=False, server_header=False, date_header=False,
                log_level="info")


if __name__ == "__main__":
    main()
