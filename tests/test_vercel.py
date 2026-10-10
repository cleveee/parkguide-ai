"""Offline checks for the hosted (Vercel) profile. No paid call, no network.

PARKGUIDE_HOSTED=1 stands in for Vercel's VERCEL=1. Every test that enables it
also points PARKGUIDE_STATE_DIR at a temporary directory.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tomllib

from fastapi.testclient import TestClient
import pytest

from parkguide import embedding_cache, runtime, store, web
from parkguide import chat as core
from parkguide.budget import Budget

ROOT = Path(__file__).resolve().parents[1]
PROD = "parkguide.vercel.app"
DEPLOY = "parkguide-abc123-robin.vercel.app"
CUSTOM = "guide.example.org"


@pytest.fixture
def hosted(monkeypatch, tmp_path):
    monkeypatch.setenv("PARKGUIDE_HOSTED", "1")
    monkeypatch.setenv("PARKGUIDE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("VERCEL_URL", DEPLOY)
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", PROD)
    monkeypatch.setenv("PARKGUIDE_PUBLIC_ORIGIN", f"https://{CUSTOM}")
    return tmp_path


def test_hosted_hosts_come_only_from_server_env(hosted, monkeypatch):
    assert web._allowed_hosts() == {DEPLOY, PROD, CUSTOM}
    assert web._allowed_origins() == {f"https://{DEPLOY}", f"https://{PROD}", f"https://{CUSTOM}"}
    for bad in ("https://*.vercel.app", "http://guide.example.org", "https://guide.example.org/path",
                "https://user@guide.example.org", "https://guide.example.org:8443", "guide.example.org", "https://localhost"):
        monkeypatch.setenv("PARKGUIDE_PUBLIC_ORIGIN", bad)
        assert web._allowed_hosts() == {DEPLOY, PROD}, bad
    monkeypatch.setenv("VERCEL_URL", "*.vercel.app")
    assert web._allowed_hosts() == {PROD}


def test_hosted_guard_rejects_foreign_hosts_and_origins(hosted):
    client = TestClient(web.app, base_url=f"https://{PROD}")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").json()["profile"] == "vercel"
    for host in ("evil.vercel.app", "127.0.0.1:8513"):
        assert client.get("/api/health", headers={"Host": host}).status_code == 421
    spoof = client.get("/api/health", headers={"Host": "evil.vercel.app", "X-Forwarded-Host": PROD})
    assert spoof.status_code == 421
    body = {"Content-Type": "application/json"}
    # Passing the guard reaches the unknown-API 404; failing it is 403.
    assert client.post("/api/x", content="{}", headers={**body, "Origin": f"https://{PROD}"}).status_code == 404
    assert client.post("/api/x", content="{}", headers={**body, "Origin": f"https://{CUSTOM}"}).status_code == 403
    assert client.post("/api/x", content="{}", headers={**body, "Origin": f"https://{DEPLOY}"}).status_code == 403
    custom_client = TestClient(web.app, base_url=f"https://{CUSTOM}")
    assert custom_client.post("/api/x", content="{}", headers={**body, "Origin": f"https://{CUSTOM}"}).status_code == 404
    for origin in (None, f"http://{PROD}", "https://evil.vercel.app", "null"):
        headers = body if origin is None else {**body, "Origin": origin}
        assert client.post("/api/x", content="{}", headers=headers).status_code == 403, origin
    large = client.post("/api/x", content="x" * (web.MAX_BODY_BYTES + 1), headers={**body, "Origin": f"https://{PROD}"})
    assert large.status_code == 413


def test_local_profile_unchanged(monkeypatch):
    for name in ("VERCEL", "PARKGUIDE_HOSTED"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VERCEL_URL", DEPLOY)
    assert web._allowed_hosts() == web.ALLOWED_HOSTS
    assert runtime.ledger_path() == ROOT / "artifacts/api-ledger.json"
    assert runtime.embedding_cache_dir() == ROOT / "data/embedding-cache"
    assert runtime.rerank_override() is None
    assert runtime.runtime_profile()["rerank_enabled"] is True


def test_hosted_writes_go_to_temp(hosted, tmp_path):
    state = tmp_path / "state"
    assert Budget().path == state / "api-ledger.json"
    assert web.ledger_path() == state / "api-ledger.json"
    assert embedding_cache.cache_folder().parent == state / "embedding-cache"
    # Custom roots used by unit tests keep their own ledger; pricing stays bundled.
    assert Budget(tmp_path / "custom").path == tmp_path / "custom/artifacts/api-ledger.json"
    budget = Budget(cap=1.0)
    assert budget.rates("embedding")
    budget.settle(budget.reserve("embedding", 10), 10)
    event = json.loads((state / "api-ledger.json").read_text())["events"][0]
    assert event["status"] == "reported_usage"
    assert set(event) == {"id", "kind", "timestamp", "status", "cost_estimate_usd", "rates", "input_tokens", "output_tokens"}
    profile = runtime.runtime_profile()
    assert profile["budget"]["scope"] == "per_instance" and "not a global" in profile["budget"]["note"]


def test_hosted_database_is_read_only_and_never_created(hosted, tmp_path):
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError):
        with store._connection(missing):
            pass
    assert not missing.exists()
    db = tmp_path / "fixture.sqlite"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE t (x)")
    connection.commit()
    connection.close()
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        with store._connection(db) as connection:
            connection.execute("INSERT INTO t VALUES (1)")
    with store._connection(db) as connection:
        assert connection.execute("SELECT count(*) FROM t").fetchone()[0] == 0


def test_web_reports_missing_database(hosted, monkeypatch, tmp_path):
    monkeypatch.setattr(web, "database", lambda: tmp_path / "absent.sqlite")
    with pytest.raises(web.WebError) as error:
        with web._connect():
            pass
    assert error.value.code == "database_missing"
    assert not (tmp_path / "absent.sqlite").exists()


def test_hosted_chat_forces_rerank_off_and_reports_profile(hosted, monkeypatch):
    seen = {}

    def fake_answer(question, history, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop before any paid call")

    monkeypatch.setattr(core, "gold_drafts_ready", lambda: True)
    monkeypatch.setattr(web, "active_structure_build", lambda: {"build_id": "b" * 64, "strategy": "structure"})
    monkeypatch.setattr(core, "answer", fake_answer)
    with pytest.raises(web.WebError) as error:
        web.run_chat(web.ChatRequest(selected_park="yose", question="When is Glacier Point Road open?"))
    assert seen["rerank"] is False
    runtime_details = error.value.details["runtime"]
    assert runtime_details["profile"] == "vercel" and runtime_details["rerank_enabled"] is False
    assert runtime_details["budget_scope"] == "per_instance"


def test_hosted_meta_exposes_profile(hosted):
    meta = TestClient(web.app, base_url=f"https://{PROD}").get("/api/meta").json()
    assert meta["runtime"]["profile"] == "vercel"
    assert meta["runtime"]["rerank_enabled"] is False and meta["models"]["reranker"]["enabled"] is False
    assert meta["retrieval"]["selected_park_rerank"] is False
    assert "do not measure" in meta["runtime"]["evaluation_note"]
    assert meta["totals"]["documents"] == 155 and meta["totals"]["chunks_all_builds"] == 5405
    assert "/tmp/parkguide" in meta["local_persistence"]["budget_ledger"]


def test_packaging_configuration():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["tool"]["vercel"]["entrypoint"] == "server:app"
    assert pyproject["project"]["requires-python"] == ">=3.12,<3.14"
    runtime_deps = " ".join(pyproject["project"]["dependencies"]).lower()
    requirements = " ".join(line for line in (ROOT / "requirements.txt").read_text().lower().splitlines()
                            if not line.startswith("#"))
    for heavy in ("torch", "sentence-transformers", "streamlit", "pdfplumber", "transformers"):
        assert heavy not in runtime_deps and heavy not in requirements
    for needed in ("fastapi", "numpy", "rank-bm25", "openai", "httpx", "tiktoken", "requests", "python-dotenv", "beautifulsoup4"):
        assert needed in requirements
    vercel = json.loads((ROOT / "vercel.json").read_text())
    assert vercel["framework"] == "fastapi"
    # CDN-served HTML and the local/API shell must permit the same preview assets.
    csp = next(header["value"] for rule in vercel["headers"] for header in rule["headers"]
               if header["key"] == "Content-Security-Policy")
    assert csp == web._CSP
    function = vercel["functions"]["server.py"]
    assert len(function["excludeFiles"]) <= 256
    # A real hosted build returned 404 for JS/CSS when only index.html was bundled.
    assert "public/**" in function["includeFiles"]
    assert "public/assets" not in function["excludeFiles"]
    for path in ("data/parkguide.sqlite", "data/evaluation/gold-draft-manifest.json",
                 "data/evaluation/gold-drafts.jsonl", "config/**", "vendor/tiktoken/**"):
        assert path in function["includeFiles"]
    assert "data/raw/*.html" in function["includeFiles"]
    assert "data/raw/*.{pdf,jsonl,bin}" in function["excludeFiles"]
    for path in ("web/**", "data/embedding-cache/**", "artifacts/**", "tests/**", "app.py"):
        assert path in function["excludeFiles"]
    assert "prepare_vercel.py" in vercel["buildCommand"]
    ignore = (ROOT / ".vercelignore").read_text().splitlines()
    assert "public/" not in ignore
    assert "data/raw/" not in ignore
    assert {"app.py", "data/raw/*.pdf", "data/raw/*.jsonl", "artifacts/", "data/evaluation/*", ".env"} <= set(ignore)
    assert {"!data/evaluation/gold-draft-manifest.json", "!data/evaluation/gold-drafts.jsonl"} <= set(ignore)


def test_tokenizer_cache_name_and_server_entrypoint():
    assert runtime.CL100K_CACHE_FILE == hashlib.sha1(runtime.CL100K_URL.encode()).hexdigest()
    cached = runtime.TIKTOKEN_DIR / runtime.CL100K_CACHE_FILE
    if cached.is_file():  # Present after scripts/prepare_vercel.py has run.
        assert hashlib.sha256(cached.read_bytes()).hexdigest() == \
            "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
    source = (ROOT / "server.py").read_text()
    assert source.index("from parkguide import runtime") < source.index("from parkguide.web import app")


def test_publish_frontend_copies_only_dist(tmp_path):
    spec = importlib.util.spec_from_file_location("prepare_vercel", ROOT / "scripts/prepare_vercel.py")
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    dist, public = tmp_path / "dist", tmp_path / "public"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>")
    (dist / "assets/app.js").write_text("1")
    (public / "stale.txt").parent.mkdir()
    (public / "stale.txt").write_text("old")
    assert prepare.publish_frontend(dist, public) == ["assets/app.js", "index.html"]
    (dist / "leak.sqlite").write_text("x")
    with pytest.raises(SystemExit):
        prepare.publish_frontend(dist, public)
