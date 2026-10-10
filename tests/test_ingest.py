"""Offline ingestion contracts: provenance, structure, source bounds and rates."""

import hashlib
import json
from pathlib import Path

import pytest

from parkguide.ingest import IngestionGateError, canonicalize_url, ingest_corpus, ingest_document, is_allowed_url


FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.nps.gov/yose/planyourvisit/fees.htm"


def config(**updates):
    return {
        "allowed_host": "www.nps.gov", "allowed_path_prefixes": ["/yose/planyourvisit/"],
        "additional_public_pdf_paths": ["/common/uploads/"], "seeds": [URL],
        "crawler_user_agent": "ParkGuideFixture/0.1", "crawler_contact_email": "crawler@example.org",
        "instructor_domain_approval": "approved", "requests_per_second": 1,
        "minimum_table_documents": 1, **updates,
    }


def test_html_cleaning_table_headers_dates_contacts_and_offsets():
    raw = (FIXTURES / "visitor.html").read_bytes()
    doc = ingest_document(raw, URL + "?utm_source=fixture#fees", "2026-10-09T00:00:00Z", "text/html")
    assert doc["source_url"] == URL
    assert doc["doc_id"] == hashlib.sha256(URL.encode()).hexdigest()
    assert doc["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert doc["effective_date"] == "2026-10-09"
    assert doc["has_table"] and doc["page_type"] == "html"
    assert sum(block["kind"] == "table" for block in doc["blocks"]) == 1
    assert "Navigation content" not in doc["normalized_text"] and "Footer repeated" not in doc["normalized_text"]
    assert "person@example.org" not in doc["normalized_text"] and "555-123-4567" not in doc["normalized_text"]
    table = next(block for block in doc["blocks"] if block["kind"] == "table")
    assert "| Pass | Price | Validity |" in table["text"]
    assert "| Vehicle | $35 | 7 days |" in table["text"]
    assert table["heading_path"] == "Visitor fees > Pass comparison"
    assert json.loads(doc["normalized_blocks_json"]) == doc["blocks"]
    for block in doc["blocks"]:
        assert doc["normalized_text"][block["start"]:block["end"]] == block["text"]
    repeated = ingest_document(raw, URL, "2026-10-10T00:00:00Z", "text/html")
    assert repeated["doc_id"] == doc["doc_id"] and repeated["content_hash"] == doc["content_hash"]


def test_selectable_pdf_preserves_table_and_page_reference():
    doc = ingest_document((FIXTURES / "visitor.pdf").read_bytes(), "https://www.nps.gov/common/uploads/visitor.pdf", "2026-10-09T00:00:00Z", "application/pdf")
    assert doc["page_type"] == "pdf" and doc["has_table"]
    assert doc["effective_date"] == "2026-10-09"
    assert "PDF page 1" in doc["blocks"][0]["heading_path"]
    table = next(block for block in doc["blocks"] if block["kind"] == "table")
    assert "| Pass | Price |" in table["text"] and "| Vehicle | $35 |" in table["text"]
    assert "| Annual | $70 |" in table["text"]
    for block in doc["blocks"]:
        assert doc["normalized_text"][block["start"]:block["end"]] == block["text"]


def test_merged_header_and_body_cells_keep_column_alignment():
    doc = ingest_document((FIXTURES / "merged_headers.html").read_bytes(), URL, "2026-10-09T00:00:00Z", "text/html")
    table = next(block for block in doc["blocks"] if block["kind"] == "table")
    assert "| Facility | Status | Summer 2026 / First Day | Summer 2026 / Last Day | Winter 2026-27 / First Day | Winter 2026-27 / Last Day |" in table["text"]
    assert "| Invented Campground | Closed | May 15 | September 13 | — | — |" in table["text"]
    assert "| Invented Marina | Limited | June 13 | September 19 | — | — |" in table["text"]
    assert len(table["text"].splitlines()) == 5
    assert doc["normalized_text"][table["start"]:table["end"]] == table["text"]


@pytest.mark.parametrize("url", [
    "https://www.nps.gov.evil.invalid/yose/planyourvisit/fees.htm",
    "https://www.nps.gov/yose/planyourvisit/people/director.htm",
    "https://www.nps.gov/yose/planyourvisit/login.htm",
    "https://www.nps.gov/yose/planyourvisit/%2e%2e/people.htm",
    "https://user:pass@www.nps.gov/yose/planyourvisit/fees.htm",
    "http://www.nps.gov/yose/planyourvisit/fees.htm",
    "https://www.nps.gov/unapproved/fees.htm",
])
def test_exact_host_paths_and_private_routes_are_excluded(url):
    assert not is_allowed_url(url, config())
    assert is_allowed_url("https://www.nps.gov/common/uploads/visitor.pdf?download=1", config())
    assert not is_allowed_url("https://www.nps.gov/common/uploads/visitor.html", config())


@pytest.mark.parametrize("updates", [
    {"crawler_contact_email": None}, {"instructor_domain_approval": "not_verified"},
    {"requests_per_second": 2},
])
def test_missing_human_inputs_prevent_any_fetch_or_data_creation(tmp_path, monkeypatch, updates):
    monkeypatch.setattr("parkguide.ingest.requests.Session", lambda: pytest.fail("Gate must run before session creation"))
    with pytest.raises(IngestionGateError):
        ingest_corpus(tmp_path, config(**updates), max_html=1, max_pdf=0)
    assert not (tmp_path / "data").exists()


class FakeClock:
    now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def fake_network(monkeypatch, replies, clock):
    starts = []

    class Response:
        def __init__(self, raw, status=200, content_type="text/html", headers=None):
            self.content = raw
            self.status_code = status
            self.headers = {"Content-Type": content_type, **(headers or {})}

    class Session:
        headers = {}

        def get(self, url, **kwargs):
            assert not kwargs["allow_redirects"]
            starts.append((url, clock.monotonic()))
            reply = replies[url]
            if isinstance(reply, list):
                reply = reply.pop(0)
            return Response(*reply)

        def close(self):
            pass

    monkeypatch.setattr("parkguide.ingest.requests.Session", Session)
    monkeypatch.setattr("parkguide.ingest.time.monotonic", clock.monotonic)
    monkeypatch.setattr("parkguide.ingest.time.sleep", clock.sleep)
    return starts


def test_crawl_saves_raw_before_parse_retries_rate_limits_and_deduplicates(tmp_path, monkeypatch):
    raw = (FIXTURES / "visitor.html").read_bytes()
    second = URL.replace("fees.htm", "duplicate.htm")
    starts = fake_network(monkeypatch, {
        "https://www.nps.gov/robots.txt": (b"User-agent: *\nDisallow:\n", 200, "text/plain"),
        URL: [(b"temporary", 503), (raw,)], second: (raw,),
    }, FakeClock())
    from parkguide import ingest
    original = ingest.ingest_document

    def inspect_saved_before_parse(*args):
        records = [json.loads(line) for line in (tmp_path / "data/raw/manifest.jsonl").read_text().splitlines()]
        assert any(record["raw_sha256"] == hashlib.sha256(args[0]).hexdigest() and (tmp_path / record["raw_path"]).exists() for record in records)
        return original(*args)

    monkeypatch.setattr(ingest, "ingest_document", inspect_saved_before_parse)
    summary = ingest_corpus(tmp_path, config(seeds=[URL, second]), max_html=2, max_pdf=0)
    assert summary["status"] == "incomplete"
    assert summary["counts"]["usable_html"] == 1
    assert summary["counts"]["duplicate_documents_this_run"] == 1
    assert summary["counts"]["request_attempts_this_run"] == 4
    assert all(next_start - prior_start >= 1 for (_, prior_start), (_, next_start) in zip(starts, starts[1:]))
    assert len((tmp_path / "data/documents.jsonl").read_text().splitlines()) == 1


def test_robots_denial_never_fetches_document(tmp_path, monkeypatch):
    starts = fake_network(monkeypatch, {"https://www.nps.gov/robots.txt": (b"User-agent: *\nDisallow: /yose/\n", 200, "text/plain")}, FakeClock())
    summary = ingest_corpus(tmp_path, config(), max_html=1, max_pdf=0)
    assert [url for url, _ in starts] == ["https://www.nps.gov/robots.txt"]
    assert summary["rejections"] == [{"url": URL, "reason": "robots_denied"}]


def test_external_redirect_is_not_followed(tmp_path, monkeypatch):
    starts = fake_network(monkeypatch, {
        "https://www.nps.gov/robots.txt": (b"User-agent: *\nDisallow:\n", 200, "text/plain"),
        URL: (b"redirect", 302, "text/html", {"Location": "https://external.invalid/private"}),
    }, FakeClock())
    summary = ingest_corpus(tmp_path, config(), max_html=1, max_pdf=0)
    assert len(starts) == 2 and summary["rejections"][0]["reason"] == "outside_allowlist"


def test_resume_uses_saved_raw_and_does_not_fetch_again(tmp_path, monkeypatch):
    raw = (FIXTURES / "visitor.html").read_bytes()
    starts = fake_network(monkeypatch, {
        "https://www.nps.gov/robots.txt": (b"User-agent: *\nDisallow:\n", 200, "text/plain"), URL: (raw,),
    }, FakeClock())
    assert ingest_corpus(tmp_path, config(), max_html=1, max_pdf=0)["status"] == "complete"
    count = len(starts)
    second_run = ingest_corpus(tmp_path, config(), max_html=1, max_pdf=0)
    assert second_run["status"] == "complete" and second_run["counts"]["request_attempts_this_run"] == 0
    assert len(starts) == count
