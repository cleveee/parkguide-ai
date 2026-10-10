"""Offline regression for equal-size HTML builds with Vercel-normalized mtimes."""
import os

from fastapi.responses import FileResponse
from fastapi.testclient import TestClient
import pytest

from parkguide import web


@pytest.fixture(params=[False, True], ids=["local", "hosted"])
def frontend_client(request, tmp_path, monkeypatch):
    monkeypatch.setattr(web, "DIST", tmp_path)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("PARKGUIDE_HOSTED", raising=False)
    base = "http://127.0.0.1:8513"
    if request.param:
        monkeypatch.setenv("PARKGUIDE_HOSTED", "1")
        monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "parkguide.vercel.app")
        base = "https://parkguide.vercel.app"
    return TestClient(web.app, base_url=base), tmp_path


@pytest.mark.parametrize("path", ["/", "/index.html", "/corpus"])
def test_new_shell_is_not_revalidated_using_old_file_metadata(frontend_client, path):
    client, dist = frontend_client
    index = dist / "index.html"
    old = '<!doctype html><script src="/assets/old.js"></script>'
    new = '<!doctype html><script src="/assets/new.js"></script>'
    timestamp = 1_540_000_000
    assert len(old) == len(new)

    index.write_text(old)
    os.utime(index, (timestamp, timestamp))
    legacy = FileResponse(index, stat_result=index.stat())
    assert client.get(path).text == old

    # Vercel gives both builds the same timestamp. FileResponse's metadata-based
    # validators therefore collide, even though the referenced bundle changed.
    index.write_text(new)
    os.utime(index, (timestamp, timestamp))
    replacement = FileResponse(index, stat_result=index.stat())
    assert legacy.headers["etag"] == replacement.headers["etag"]
    response = client.get(path, headers={
        "If-None-Match": legacy.headers["etag"],
        "If-Modified-Since": legacy.headers["last-modified"],
    })
    assert response.status_code == 200
    assert response.text == new
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    assert "last-modified" not in response.headers


def test_hashed_assets_keep_immutable_cache(frontend_client):
    client, dist = frontend_client
    (dist / "index.html").write_text("<!doctype html>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app-a1b2.js").write_text("console.log('fixture')")
    response = client.get("/assets/app-a1b2.js")
    assert response.status_code == 200
    assert response.text == "console.log('fixture')"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
