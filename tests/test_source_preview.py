"""The preview must retain evidence without executing source-page content."""
from hashlib import sha256

from bs4 import BeautifulSoup
import pytest

from parkguide.source_preview import PreviewUnavailable, live_website, readable_html, source_preview, website_html


def test_preview_keeps_inline_evidence_and_table_structure_without_active_content():
    raw = b'''<main onclick="steal()"><h1>Pets</h1><p>Dogs are <strong onmouseover="steal()">not allowed</strong> on trails.</p><!-- fake source words --><div class="ParkFooter">Contact us</div><script>alert(1)</script><iframe src="https://evil.test"></iframe><a href="javascript:steal()">More</a><form>Sign in<input></form><table><tr><th colspan="2">Rule</th></tr><tr><td style="background:url(https://evil.test)">Leash</td><td>6 feet</td></tr></table></main>'''
    markup = readable_html(raw)
    soup = BeautifulSoup(markup, "html.parser")
    assert soup.p.get_text() == "Dogs are not allowed on trails."
    assert soup.table.find("th")["colspan"] == "2"
    assert soup.find("script") is None and soup.find("iframe") is None
    assert soup.find("form") is None
    assert "fake source words" not in markup and "Contact us" not in markup
    assert all(set(node.attrs) <= {"colspan", "rowspan"} for node in soup.find_all(True))


def test_preview_keeps_findable_collapsed_evidence():
    raw = b'<main><div hidden="until-found"><p>Pets are not allowed on most trails.</p></div><div hidden>Navigation placeholder</div></main>'
    markup = readable_html(raw)
    assert 'Pets are not allowed on most trails.' in markup
    assert 'Navigation placeholder' not in markup
    assert 'hidden' not in markup


def test_full_website_keeps_original_layout_and_assets_without_source_scripts():
    raw = b'''<html><head><base href="https://evil.test"><meta http-equiv="refresh" content="0;url=https://evil.test"><link rel="stylesheet" href="/styles/nps.css"><link rel="stylesheet" href="https://evil.test/steal.css"><style>.nps{color:green}</style><script>alert(1)</script></head><body class="nps" onload="steal()"><header>National Park Service</header><main><div class="usa-accordion__content" hidden="until-found"><p>Dogs are <strong>not allowed</strong> on trails.</p></div><img src="/images/dog.jpg" onerror="steal()"><a href="/yose/planyourvisit/pets.htm" onclick="steal()">Pets</a><a href="javascript:steal()">Unsafe link</a><img src="https://www.nps.gov:bad/dog.jpg"><iframe srcdoc="evil"></iframe><object data="evil"></object><form>Search<input></form></main></body></html>'''
    soup = BeautifulSoup(website_html(raw, 'https://www.nps.gov/yose/planyourvisit/index.htm'), 'html.parser')
    assert soup.body['class'] == ['nps'] and soup.header.get_text() == 'National Park Service'
    assert soup.find('link')['href'] == 'https://www.nps.gov/styles/nps.css'
    assert len(soup.find_all('link')) == 1
    assert soup.img['src'] == 'https://www.nps.gov/images/dog.jpg'
    assert soup.find('strong').get_text() == 'not allowed'
    assert soup.find('div')['hidden'] == 'until-found'
    assert soup.find('style').get_text() == '.nps{color:green}'
    assert soup.base['href'] == 'https://www.nps.gov/yose/planyourvisit/index.htm'
    assert "script-src 'none'" in soup.find('meta', attrs={'http-equiv':'Content-Security-Policy'})['content']
    assert soup.find('a')['target'] == '_blank'
    assert 'href' not in soup.find_all('a')[1].attrs
    assert soup.find('script') is None and soup.find('iframe') is None and soup.find('object') is None and soup.find('form') is None
    assert not soup.find('meta', attrs={'http-equiv':'refresh'})
    assert not any(key.startswith('on') for node in soup.find_all(True) for key in node.attrs)


def test_live_preview_fetches_only_known_nps_urls_and_refuses_redirects(monkeypatch):
    import parkguide.source_preview as previews
    calls = []
    class Response:
        status_code = 200
        headers = {'Content-Type':'text/html;charset=UTF-8'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, chunk_size): yield b'<html><body><p>Keep dogs on a leash.</p></body></html>'
    response = Response()
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return response
    monkeypatch.setattr(previews.requests, 'get', get)
    for url in ('http://127.0.0.1/secret', 'https://www.nps.gov@evil.test/yose/planyourvisit/pets.htm', 'https://www.nps.gov/yose/planyourvisit/../../secret'):
        with pytest.raises(PreviewUnavailable): live_website(url)
    assert calls == []
    assert 'Keep dogs on a leash.' in live_website('https://www.nps.gov/yose/planyourvisit/pets.htm')
    assert calls[0][1]['allow_redirects'] is False
    assert calls[0][1]['timeout'] == (3, 8)
    response.status_code = 302
    with pytest.raises(PreviewUnavailable): live_website('https://www.nps.gov/yose/planyourvisit/pets.htm')
    response.status_code = 200
    response.iter_content = lambda chunk_size: iter([b'x' * (2 * 1024 * 1024 + 1)])
    with pytest.raises(PreviewUnavailable): live_website('https://www.nps.gov/yose/planyourvisit/pets.htm')


def test_preview_cannot_select_arbitrary_files_and_checks_saved_bytes(tmp_path):
    document = {"page_type": "html"}
    with pytest.raises(PreviewUnavailable):
        source_preview(tmp_path, document, {"raw_sha256": "../secret"})
    digest = sha256(b"<main><p>Saved evidence</p></main>").hexdigest()
    path = tmp_path / "data/raw" / (digest + ".html")
    path.parent.mkdir(parents=True)
    with pytest.raises(PreviewUnavailable):
        source_preview(tmp_path, document, {"raw_sha256": digest})
    path.write_bytes(b"<main><p>Changed evidence</p></main>")
    with pytest.raises(PreviewUnavailable):
        source_preview(tmp_path, document, {"raw_sha256": digest})
    path.write_bytes(b"<main><p>Saved evidence</p></main>")
    assert "Saved evidence" in source_preview(tmp_path, document, {"raw_sha256": digest})["html"]


def test_pdf_preview_labels_the_extraction_and_escapes_source_text(tmp_path):
    preview = source_preview(tmp_path, {"page_type": "pdf"}, {"blocks": [{"heading_path": "PDF page 7", "text": "<script>alert(1)</script>"}]})
    assert preview["mode"] == "pdf_text"
    assert "&lt;script&gt;" in preview["html"]


def test_preview_route_uses_document_identity_and_reports_missing_raw_file(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from parkguide import web
    from parkguide.store import save_documents
    raw = b"<main><h1>Pets</h1><p>Keep dogs on a leash.</p></main>"
    digest = sha256(raw).hexdigest()
    identifier = "a" * 64
    db = tmp_path / "fixture.sqlite"
    save_documents(db, [{"doc_id": identifier, "source_url": "https://www.nps.gov/yose/planyourvisit/pets.htm", "content_hash": "b" * 64,
                         "title": "Pets", "page_type": "html", "crawled_at": "2026-10-10T02:00:00+00:00",
                         "normalized_text": "Keep dogs on a leash.", "blocks": [], "raw_sha256": digest}])
    monkeypatch.setattr(web, "database", lambda: db)
    monkeypatch.setattr(web, "ROOT", tmp_path)
    client = TestClient(web.app, base_url="http://127.0.0.1:8513")
    assert client.get("/api/documents/" + "c" * 64 + "/preview").status_code == 404
    response = client.get("/api/documents/" + identifier + "/preview")
    assert response.status_code == 409 and response.json()["error"]["code"] == "preview_unavailable"
    path = tmp_path / "data/raw" / (digest + ".html")
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    response = client.get("/api/documents/" + identifier + "/preview")
    assert response.status_code == 200
    assert response.json()["doc_id"] == identifier
    assert response.json()["html"] == "<h1>Pets</h1><p>Keep dogs on a leash.</p>"
    assert "frame-src 'self' https://www.nps.gov;" in response.headers["content-security-policy"]
    import parkguide.source_preview as previews
    monkeypatch.setattr(previews, 'live_website', lambda url: '<html><body>Live NPS page</body></html>')
    live = client.get('/api/documents/' + identifier + '/preview?view=website')
    assert live.status_code == 200 and live.json()['mode'] == 'html_page'
    assert live.json()['content_origin'] == 'live' and live.json()['loaded_at']
    assert live.json()['crawled_at'] == '2026-10-10T02:00:00+00:00'
