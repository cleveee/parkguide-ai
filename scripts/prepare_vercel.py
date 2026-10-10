"""Vercel build step: verify the frozen bundle, cache the tokenizer, publish the SPA.

Runs after `npm --prefix web ci && npm --prefix web run build`. It makes no
Azure call and never builds, migrates or re-embeds the index. The only network
access allowed is tiktoken's download of the public cl100k_base file when the
vendored cache is absent; tiktoken verifies that file's SHA-256.
"""
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DB = ROOT / "data/parkguide.sqlite"
DB_BYTES = 56_664_064
DB_SHA256 = "2e017b08ae4a358944716da3b62357b70c988bb61feebe62c39b9b0160feba5c"
DB_COUNTS = {"documents": 155, "chunks": 5405, "embeddings": 5405, "index_builds": 2}
GOLD_SEAL = ("data/evaluation/gold-draft-manifest.json", "data/evaluation/gold-drafts.jsonl")
# Never copied to the public CDN directory.
SERVER_ONLY_SUFFIXES = {".sqlite", ".jsonl", ".env", ".py", ".lock", ".tiktoken"}


def verify_database(path=DB):
    if not path.is_file() or path.stat().st_size != DB_BYTES:
        raise SystemExit(f"Frozen database missing or wrong size: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != DB_SHA256:
        raise SystemExit("Frozen database SHA-256 differs; refusing to deploy a rebuilt index")
    connection = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        counts = {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in DB_COUNTS}
        active = connection.execute("SELECT json_extract(manifest_json, '$.strategy') FROM index_builds WHERE active=1").fetchall()
    finally:
        connection.close()
    if counts != DB_COUNTS or active != [("structure",)]:
        raise SystemExit(f"Frozen database counts differ: {counts}, active={active}")
    return counts


def cache_tokenizer():
    from parkguide import runtime
    os.environ["TIKTOKEN_CACHE_DIR"] = str(runtime.TIKTOKEN_DIR)
    runtime.TIKTOKEN_DIR.mkdir(parents=True, exist_ok=True)
    import tiktoken
    tiktoken.get_encoding("cl100k_base")
    cached = runtime.TIKTOKEN_DIR / runtime.CL100K_CACHE_FILE
    if not cached.is_file():
        raise SystemExit("cl100k_base tokenizer cache was not written")
    return cached


def publish_frontend(dist=ROOT / "web/dist", public=ROOT / "public"):
    """Copy only the built SPA to public/ for the CDN."""
    if not (dist / "index.html").is_file():
        raise SystemExit("web/dist/index.html is missing; run the frontend build first")
    leaked = [path for path in dist.rglob("*") if path.is_file() and path.suffix in SERVER_ONLY_SUFFIXES]
    if leaked:
        raise SystemExit(f"Refusing to publish server-only files: {leaked}")
    if public.exists():
        shutil.rmtree(public)
    shutil.copytree(dist, public)
    return sorted(str(path.relative_to(public)) for path in public.rglob("*") if path.is_file())


def main():
    counts = verify_database()
    missing = [name for name in GOLD_SEAL if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit(f"Gold seal files missing: {missing}")
    from parkguide.chat import gold_drafts_ready
    if not gold_drafts_ready():
        raise SystemExit("Gold drafts are not frozen; hosted chat would be disabled")
    cached = cache_tokenizer()
    files = publish_frontend()
    print(f"Frozen database verified: {counts}")
    print(f"Tokenizer cache: {cached.relative_to(ROOT)} ({cached.stat().st_size} bytes)")
    print(f"Published {len(files)} frontend files to public/")


if __name__ == "__main__":
    main()
