"""Vercel entrypoint ([tool.vercel] entrypoint = "server:app").

Thin wrapper around parkguide.web.app. The legacy Streamlit app.py is not an
entrypoint. On Vercel (VERCEL=1) parkguide.runtime selects the hosted profile:
read-only bundled SQLite, /tmp per-instance cache and ledger, bundled tokenizer
and no reranker. It never builds, migrates or re-embeds the index.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# Imported first so TIKTOKEN_CACHE_DIR is set before any encoding is created.
from parkguide import runtime  # noqa: E402

if runtime.hosted() and not (runtime.TIKTOKEN_DIR / runtime.CL100K_CACHE_FILE).is_file():
    raise RuntimeError("Bundled cl100k_base tokenizer cache is missing; run scripts/prepare_vercel.py at build")

from parkguide.web import app  # noqa: E402,F401
