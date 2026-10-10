"""Small verified Azure v1 embedding adapter; no application/database coupling."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
import time

import numpy as np
import requests


_local = threading.local()


def _session() -> requests.Session:
    """Reuse TLS connections within one worker; credentials stay per request."""
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


def _transport_reason(error: requests.RequestException) -> str:
    """Report only allowlisted exception classes and numeric OS error codes."""
    allowed = {
        "RequestException", "ConnectionError", "ConnectTimeout", "ReadTimeout",
        "Timeout", "SSLError", "ProxyError", "ChunkedEncodingError",
        "MaxRetryError", "NewConnectionError", "NameResolutionError",
        "ProtocolError", "ConnectionResetError", "ConnectionRefusedError",
        "RemoteDisconnected", "TimeoutError", "gaierror", "OSError",
    }
    pending, seen, classes, errnos = [error], set(), [], []
    while pending and len(seen) < 12:
        item = pending.pop()
        if not isinstance(item, BaseException) or id(item) in seen:
            continue
        seen.add(id(item))
        name = type(item).__name__
        if name in allowed and name not in classes:
            classes.append(name)
        number = getattr(item, "errno", None)
        if isinstance(number, int) and number not in errnos:
            errnos.append(number)
        pending.extend([item.__cause__, item.__context__, getattr(item, "reason", None)])
        pending.extend(value for value in item.args if isinstance(value, BaseException))
    detail = ", ".join(classes) or "RequestException"
    if errnos:
        detail += "; errno=" + ",".join(str(number) for number in errnos)
    return detail


@dataclass
class EmbeddingBatch:
    vectors: np.ndarray
    model: str
    usage: dict
    elapsed_ms: float


def embed(texts: list[str], expected_dimension: int = 1536, approved_config: dict | None = None) -> EmbeddingBatch:
    """Return ordered, finite, unit-length float32 vectors or fail safely.

    Corpus batching, cache, bounded retries, and budgets are handled by the
    caller. This adapter does not perform automatic retries.
    """
    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Embedding inputs must be nonempty strings")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    key = os.getenv("AZURE_OPENAI_API_KEY", "")
    deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "")
    if not endpoint or not key or not deployment:
        raise RuntimeError("Azure embedding configuration is incomplete")
    if approved_config is None:
        root = Path(__file__).resolve().parents[2]
        approved_config = json.loads((root / "config/project.json").read_text())["embedding"]
    if (endpoint != approved_config["endpoint"].rstrip("/")
            or deployment != approved_config["deployment"]
            or expected_dimension != approved_config["dimension"]):
        raise RuntimeError("Azure environment differs from approved configuration; no request sent")
    if not endpoint.startswith("https://") or approved_config.get("api_style", "v1") != "v1":
        raise ValueError("Only the approved HTTPS Azure v1 endpoint is supported")
    url = endpoint + "/openai/v1/embeddings"
    started = time.perf_counter()
    try:
        response = _session().post(
            url,
            headers={"api-key": key, "Content-Type": "application/json"},
            json={"model": deployment, "input": texts, "encoding_format": "float"},
            timeout=(10, 60),
            allow_redirects=False,
        )
    except requests.RequestException as error:
        if hasattr(_local, "session"):
            _local.session.close()
            del _local.session
        reason = _transport_reason(error)
        raise RuntimeError(f"Azure embedding transport failed ({reason}); response/credentials not logged") from None
    if response.status_code != 200:
        raise RuntimeError(f"Azure embedding HTTP {response.status_code}; response body not logged")
    try:
        payload = response.json()
        rows = payload["data"]
        if sorted(row["index"] for row in rows) != list(range(len(texts))):
            raise ValueError("Unexpected input/output index mapping")
        vectors = np.asarray([row["embedding"] for row in sorted(rows, key=lambda row: row["index"])], dtype=np.float32)
        if vectors.shape != (len(texts), expected_dimension) or not np.isfinite(vectors).all():
            raise ValueError("Invalid vector dimensions or values")
        norms = np.linalg.norm(vectors.astype(np.float64), axis=1)
        if not np.isfinite(norms).all() or (norms <= 0).any():
            raise ValueError("Invalid vector norm")
        vectors = (vectors / norms[:, None]).astype(np.float32)
        model = payload["model"]
        if not isinstance(model, str) or model != deployment:
            raise ValueError("Returned model differs from verified configuration")
        usage = {name: int(payload.get("usage", {}).get(name, 0)) for name in ("prompt_tokens", "total_tokens")}
    except (KeyError, TypeError, ValueError, OverflowError):
        raise RuntimeError("Azure embedding response failed schema/vector validation") from None
    return EmbeddingBatch(vectors, model, usage, round((time.perf_counter() - started) * 1000, 1))
