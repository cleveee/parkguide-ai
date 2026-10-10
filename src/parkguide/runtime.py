"""Shared configuration, artifact hashes, JSONL helpers and the runtime profile.

Two profiles exist. "local" (the default) keeps every path and behavior of the
loopback POC. "vercel" is selected by VERCEL=1 (set by Vercel) or the explicit
PARKGUIDE_HOSTED=1 test override: the bundled SQLite file is opened read-only,
the query-embedding cache and budget ledger live under an ephemeral per-instance
directory (/tmp/parkguide), the tokenizer loads from the bundled cache, and the
optional cross-encoder reranker is not installed or used.
"""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# tiktoken caches each encoding under sha1(blob URL); this is the cl100k_base file.
TIKTOKEN_DIR = ROOT / "vendor/tiktoken"
CL100K_URL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
CL100K_CACHE_FILE = hashlib.sha1(CL100K_URL.encode()).hexdigest()


def hosted():
    return os.environ.get("VERCEL") == "1" or os.environ.get("PARKGUIDE_HOSTED") == "1"


def profile():
    return "vercel" if hosted() else "local"


def configure_environment():
    """Point tiktoken at the bundled cache and keep Hugging Face offline when hosted.

    Must run before the first tiktoken.get_encoding call; this module is
    imported by budget.py before chat/store/chunking create an encoding.
    """
    if hosted():
        os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(TIKTOKEN_DIR))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


configure_environment()


def state_root():
    """Writable per-instance directory when hosted; the repository locally."""
    return Path(os.environ.get("PARKGUIDE_STATE_DIR", "/tmp/parkguide")) if hosted() else ROOT


def embedding_cache_dir():
    return state_root() / "embedding-cache" if hosted() else ROOT / "data/embedding-cache"


def ledger_path():
    return state_root() / "api-ledger.json" if hosted() else ROOT / "artifacts/api-ledger.json"


def sqlite_uri(path):
    """Read-only URI; hosted files are also immutable (read-only filesystem, no locks)."""
    return f"file:{Path(path)}?mode=ro" + ("&immutable=1" if hosted() else "")


def rerank_override():
    """None lets the shared answer path use config; hosted forces reranking off."""
    return False if hosted() else None


def runtime_profile():
    """Public, credential-free description of the effective serving profile."""
    settings = config()
    cap = settings["evaluation"]["proposed_api_budget_usd"]
    if hosted():
        return {
            "profile": "vercel",
            "rerank_enabled": False,
            "rerank_reason": "The hosted Vercel bundle does not install the optional PyTorch cross-encoder (size and cold start). "
                             "Retrieval is hybrid NumPy cosine + BM25 with reciprocal-rank fusion and the same five-passage context.",
            "evaluation_note": "Recent selected-park web checks used the local cross-encoder reranker. Historical development stages used several local retrieval variants. "
                               "They do not measure this hosted profile's retrieval accuracy.",
            "budget": {"cap_usd": cap, "scope": "per_instance",
                       "note": "Ledger lives in /tmp on each Vercel instance; it resets when the instance is recycled and is not "
                               "shared across concurrently running instances. It is not a global spending limit. Use deployment protection and provider rate/quota controls to manage exposure; Azure budget alerts alone do not enforce a hard cap."},
            "state_storage": "/tmp/parkguide (ephemeral, per instance)",
            "request_serialization": "one answer at a time per instance; instances do not coordinate",
        }
    return {
        "profile": "local",
        "rerank_enabled": bool(settings["retrieval"].get("selected_park_rerank", True)),
        "rerank_reason": "Local profile: the pinned cross-encoder reranks selected-park candidates offline from its local cache.",
        "evaluation_note": "Saved evaluations were run with this local profile.",
        "budget": {"cap_usd": cap, "scope": "local_shared_ledger",
                   "note": "One file-locked ledger in artifacts/api-ledger.json shared by every local process."},
        "state_storage": "repository data/ and artifacts/",
        "request_serialization": "one answer at a time in this server process",
    }


def config():
    return json.loads((ROOT / "config/project.json").read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_jsonl(path, rows, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
