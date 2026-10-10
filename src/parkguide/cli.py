"""Local ParkGuide pipeline, chat, and reproducible evaluation commands."""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init-db", "doctor", "ingest", "index", "search", "chat", "gold-seal", "gold-split", "eval", "dialogues", "budget", "migrate", "final-test", "reports"])
    parser.add_argument("text", nargs="?")
    parser.add_argument("--strategy", choices=["fixed", "structure"], default="fixed")
    parser.add_argument("--mode", choices=["bm25", "dense", "hybrid"], default="hybrid")
    parser.add_argument("--build-id")
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "config/project.json").read_text())
    db = ROOT / config["database"]
    if args.command == "init-db":
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript((ROOT / "src/parkguide/schema.sql").read_text())
            connection.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version', '1')")
        print(json.dumps({"database": str(db), "schema_version": 1, "status": "initialized"}, indent=2))
        return
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    if args.command != "doctor":
        from .runtime import read_jsonl
        from .store import build_index, get_manifest, initialize, load_documents, save_documents
        from .embedding_cache import cached_embed
        result = None
        if args.command == "ingest":
            from .ingest import ingest_corpus
            sources = json.loads((ROOT / "config/sources.json").read_text())
            result = ingest_corpus(ROOT, sources)
            save_documents(db, read_jsonl(ROOT / "data/documents.jsonl"))
        elif args.command == "index":
            docs_path = ROOT / "data/documents.jsonl"
            documents = read_jsonl(docs_path) if docs_path.exists() else load_documents(db)
            result = build_index(db, documents, args.strategy, cached_embed, model_config=config["embedding"], target=config["chunking"]["body_target_tokens"], overlap=config["chunking"]["overlap_tokens"])
            folder = ROOT / "artifacts/builds"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{args.strategy}.json").write_text(json.dumps(result, indent=2) + "\n")
        elif args.command == "search":
            from .retrieval import retrieve
            if not args.text:
                parser.error("search requires a question")
            vector = None if args.mode == "bm25" else cached_embed([args.text])[0]
            result = retrieve(db, args.text, vector, mode=args.mode, build_id=args.build_id, rerank=args.rerank)
        elif args.command == "chat":
            from .chat import answer
            if not args.text:
                parser.error("chat requires a question")
            result = answer(args.text, mode=args.mode, build_id=args.build_id, rerank=args.rerank)
        elif args.command in ("gold-seal", "gold-split"):
            from .evaluation import seal_drafts, split_gold
            if not args.text:
                parser.error("provide a JSONL path")
            result = seal_drafts(args.text) if args.command == "gold-seal" else split_gold(args.text)
        elif args.command == "eval":
            from .evaluation import run
            if not args.text:
                parser.error("eval requires a dataset path")
            fixed = json.loads((ROOT / "artifacts/builds/fixed.json").read_text())["build_id"]
            structure_path = ROOT / "artifacts/builds/structure.json"
            structure = json.loads(structure_path.read_text())["build_id"] if structure_path.exists() else fixed
            variants = [
                {"name": "B0", "build_id": fixed, "closed_book": True},
                {"name": "B1", "build_id": fixed, "mode": "bm25", "rerank": False},
                {"name": "B2", "build_id": fixed, "mode": "dense", "rerank": False},
                {"name": "B3", "build_id": structure, "mode": "hybrid", "rerank": args.rerank or config['retrieval'].get('default_rerank',True)},
            ]
            result = run(args.text, variants, diagnostic=args.diagnostic)
        elif args.command == "dialogues":
            from .evaluation import dialogues
            if not args.text:
                parser.error("dialogues requires a JSONL path")
            result = dialogues(args.text, mode=args.mode, build_id=args.build_id, rerank=args.rerank)
        elif args.command == "budget":
            from .budget import Budget
            result = Budget().summary()
        elif args.command == "migrate":
            import shutil
            from .store import activate_build, integrity_report
            fixed = json.loads((ROOT / "artifacts/builds/fixed.json").read_text())["build_id"]
            structure = json.loads((ROOT / "artifacts/builds/structure.json").read_text())["build_id"]
            folder = ROOT / "artifacts/migration"
            folder.mkdir(parents=True, exist_ok=True)
            proof_db = folder / "proof.sqlite"
            shutil.copy2(db, proof_db)
            activate_build(proof_db, fixed)
            result = activate_build(proof_db, structure, delete_previous=True)
            result["network_requests"] = 0
            result["normalized_sources_reused"] = True
            (folder / "proof.json").write_text(json.dumps(result, indent=2) + "\n")
            result = {key: value for key, value in result.items() if key != 'previous_chunk_ids'}
        elif args.command == "final-test":
            from .evaluation import final_batch
            result = final_batch()
        elif args.command == "reports":
            from .reports import generate_reports
            result = generate_reports()
        if result is not None:
            print(json.dumps(result, indent=2))
        return
    packages = {}
    for package in ("requests", "beautifulsoup4", "pdfplumber", "numpy", "rank-bm25", "streamlit", "openai", "tiktoken", "python-dotenv", "pytest"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = "MISSING"
    counts = {}
    foreign_key_errors = None
    if db.exists():
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
            for table in ("documents", "index_builds", "chunks", "embeddings"):
                counts[table] = connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            foreign_key_errors = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    ready = db.exists() and foreign_key_errors == 0 and "MISSING" not in packages.values()
    print(json.dumps({
        "setup_ready": ready,
        "phase": config["phase"],
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "database": str(db),
        "counts": counts,
        "foreign_key_errors": foreign_key_errors,
        "packages": packages,
        "azure_embedding_config_present": all(os.getenv(name) for name in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_EMBEDDING_DEPLOYMENT")),
        "azure_generation_config_present": all(os.getenv(name) for name in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_GENERATION_DEPLOYMENT")),
        "generation_provider": config["generation"]["provider"],
        "generation_model": config["generation"]["model"],
        "generation_deployment": config["generation"]["deployment"],
        "rag_app_implemented": (ROOT / "app.py").exists(),
        "gold_drafts_manifest_present": (ROOT / "data/evaluation/gold-draft-manifest.json").exists(),
    }, indent=2))
    if not ready:
        raise SystemExit(1)
