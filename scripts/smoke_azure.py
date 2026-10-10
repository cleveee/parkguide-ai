"""Explicit two-input synthetic Azure smoke test; never reads corpus data."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv
import numpy as np

from parkguide.azure import embed

root = Path(__file__).resolve().parents[1]
load_dotenv(root / ".env", override=False)
inputs = [
    "ParkGuide setup check: Yosemite is a national park.",
    "ParkGuide setup check: Yellowstone is a national park.",
]
batch = embed(inputs)
folder = root / "artifacts/setup"
folder.mkdir(parents=True, exist_ok=True)
vector_path = folder / "azure-project-smoke-vectors.npy"
np.save(vector_path, batch.vectors, allow_pickle=False)
report = {
    "success": True,
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "test_kind": "project_adapter_synthetic_batch",
    "input_count": len(inputs),
    "input_sha256": [hashlib.sha256(text.encode()).hexdigest() for text in inputs],
    "model": batch.model,
    "dimension": batch.vectors.shape[1],
    "dtype": str(batch.vectors.dtype),
    "finite": bool(np.isfinite(batch.vectors).all()),
    "normalized_l2_norms": np.linalg.norm(batch.vectors, axis=1).tolist(),
    "usage": batch.usage,
    "elapsed_ms": batch.elapsed_ms,
    "vector_file_sha256": hashlib.sha256(vector_path.read_bytes()).hexdigest(),
    "limitations": ["Synthetic inputs only; no throughput, retrieval, or generation assessment"],
}
(folder / "azure-project-smoke.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
