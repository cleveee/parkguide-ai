"""Validated persistent Azure vectors keyed by text and embedding identity."""
from datetime import datetime, timezone
import hashlib
import json
import time

from dotenv import load_dotenv
import numpy as np

from .azure import embed
from .budget import Budget
from .runtime import ROOT, config, digest


def cached_embed(texts):
    load_dotenv(ROOT / ".env", override=False)
    settings = config()["embedding"]
    identity = {name: settings[name] for name in settings["identity_fields"]}
    config_hash = digest(identity)
    folder = ROOT / "data/embedding-cache" / config_hash
    folder.mkdir(parents=True, exist_ok=True)
    keys = [hashlib.sha256(text.encode()).hexdigest() for text in texts]
    vectors = {}
    missing = {}
    dimension = settings["dimension"]
    for text, key in zip(texts, keys):
        path = folder / (key + ".npy")
        metadata_path = folder / (key + ".json")
        if path.exists() and metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            vector = np.load(path, allow_pickle=False)
            if (metadata["vector_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()
                    or vector.shape != (dimension,) or vector.dtype != np.float32
                    or not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector), 1, atol=1e-5)):
                raise RuntimeError("Embedding cache integrity check failed")
            vectors[key] = vector
        else:
            missing[key] = text
    items = list(missing.items())
    for offset in range(0, len(items), settings["batch_size"]):
        group = items[offset:offset + settings["batch_size"]]
        inputs = [text for _, text in group]
        budget = Budget()
        last_error = None
        for attempt in range(config()["evaluation"]["transient_retries"] + 1):
            reservation = budget.reserve("embedding", sum(len(text.encode()) for text in inputs) + 512)
            try:
                batch = embed(inputs, expected_dimension=dimension)
                budget.settle(reservation, batch.usage["prompt_tokens"])
                last_error = None
                break
            except RuntimeError as error:
                budget.settle(reservation, error=True)
                last_error = error
                retryable = any(code in str(error) for code in ("429", "500", "502", "503", "504", "transport failed"))
                if not retryable or attempt >= config()["evaluation"]["transient_retries"]:
                    raise
                time.sleep(min(2 ** attempt, 4))
        if last_error:
            raise last_error
        for (key, text), vector in zip(group, batch.vectors):
            path = folder / (key + ".npy")
            temporary = folder / (key + ".tmp.npy")
            np.save(temporary, vector, allow_pickle=False)
            temporary.replace(path)
            (folder / (key + ".json")).write_text(json.dumps({
                "text_sha256": key, "embedding_config_sha256": config_hash,
                "identity": identity, "returned_model": batch.model,
                "vector_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2) + "\n")
            vectors[key] = vector
        print(f"Embedding batch: {offset + len(group)}/{len(items)} uncached unique texts", flush=True)
    return np.stack([vectors[key] for key in keys]) if texts else np.empty((0, dimension), dtype=np.float32)
