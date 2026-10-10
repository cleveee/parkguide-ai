"""Small public-source crawler and structure-preserving document extraction."""

from collections import deque
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import time
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import pdfplumber
import requests


class IngestionGateError(ValueError):
    """Required human/source configuration is not ready for network work."""


def canonicalize_url(url: str) -> str:
    """Canonicalize the static NPS corpus URLs; queries/fragments are excluded."""
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only absolute HTTPS public URLs are supported")
    if parsed.port not in (None, 443):
        raise ValueError("Nonstandard source ports are unsupported")
    path = unquote(parsed.path or "/")
    if any(part in (".", "..") for part in path.split("/")) or "\\" in path:
        raise ValueError("Path traversal is not a public corpus URL")
    return urlunsplit(("https", parsed.hostname.lower(), quote(path, safe="/:@-._~!$&'()*+,;="), "", ""))


def is_allowed_url(url: str, config: dict) -> bool:
    try:
        canonical = canonicalize_url(url)
    except (ValueError, TypeError):
        return False
    parsed = urlsplit(canonical)
    if parsed.hostname != config.get("allowed_host", "www.nps.gov"):
        return False
    path = unquote(parsed.path).lower()
    denied = ("/people/", "/staff/", "/person/", "/directory/", "/directories/", "/login", "/signin", "/profile/", "/users/")
    if any(part in path for part in denied):
        return False
    prefixes = config.get("allowed_path_prefixes", [])
    if any(unquote(parsed.path).startswith(prefix) for prefix in prefixes):
        return not re.search(r"\.(?:jpe?g|png|gif|svg|webp|zip|mp[34]|css|js)$", path)
    if path.endswith(".pdf"):
        return any(unquote(parsed.path) == item or unquote(parsed.path).startswith(item.rstrip("/") + "/") for item in config.get("additional_public_pdf_paths", []))
    return False


def _sha(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def redact_contacts(text: str) -> str:
    """Conservatively remove email/phone text; this is not a general PII detector."""
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[email redacted]", text, flags=re.I)
    return re.sub(r"(?<!\w)(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}(?:\s*(?:ext\.?|x)\s*\d+)?(?!\w)", "[phone redacted]", text, flags=re.I)


def _text(value: str) -> str:
    return redact_contacts(re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip())


def _table(rows: list[list]) -> str:
    clean = [[_text(str(cell or "")).replace("|", "\\|") for cell in row] for row in rows]
    clean = [row for row in clean if any(row)]
    if not clean:
        return ""
    width = max(map(len, clean))
    clean = [row + [""] * (width - len(row)) for row in clean]
    header = clean[0]
    header = [cell or f"Column {i + 1}" for i, cell in enumerate(header)]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    return "\n".join(lines + ["| " + " | ".join(row) + " |" for row in clean[1:]])


def _html_table(table) -> str:
    """Expand merged cells, then combine multirow column headers in place."""
    source_rows = [row for row in table.find_all("tr") if row.find_parent("table") is table]
    if not source_rows:
        return ""

    def span(cell, name):
        try:
            return max(1, min(int(cell.get(name, 1)), 50))
        except (ValueError, TypeError):
            return 1

    first_cells = source_rows[0].find_all(["th", "td"], recursive=False)
    header_count = max((span(cell, "rowspan") for cell in first_cells), default=1)
    thead = table.find("thead", recursive=False)
    if thead:
        header_count = max(header_count, len(thead.find_all("tr")))
    elif first_cells and all(cell.name == "th" for cell in first_cells):
        consecutive_headers = 1
        for row in source_rows[1:]:
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells or not all(cell.name == "th" for cell in cells):
                break
            consecutive_headers += 1
        header_count = max(header_count, consecutive_headers)
    grid: dict[tuple[int, int], str] = {}
    width = 0
    for row_number, row in enumerate(source_rows):
        column = 0
        for cell in row.find_all(["th", "td"], recursive=False):
            while (row_number, column) in grid:
                column += 1
            value = cell.get_text(" ", strip=True)
            rows, columns = span(cell, "rowspan"), span(cell, "colspan")
            for r in range(row_number, min(row_number + rows, len(source_rows))):
                for c in range(column, column + columns):
                    grid[r, c] = value
            column += columns
            width = max(width, column)
    expanded = [[grid.get((r, c), "") for c in range(width)] for r in range(len(source_rows))]
    header_count = min(header_count, len(expanded))
    header = [" / ".join(dict.fromkeys(row[c] for row in expanded[:header_count] if row[c].strip())) for c in range(width)]
    return _table([header, *expanded[header_count:]])


def _date_from_html(soup: BeautifulSoup) -> str | None:
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").lower()
        if name in ("date", "datepublished", "datemodified", "article:published_time", "article:modified_time", "dcterms.created", "dcterms.modified"):
            match = re.search(r"\d{4}-\d{2}-\d{2}", meta.get("content", ""))
            if match:
                return match.group(0)
    updated = re.search(r"Last updated:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", soup.get_text(" ", strip=True), re.I)
    if updated:
        try:
            return datetime.strptime(updated.group(1), "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    return None


def _html_blocks(raw: bytes) -> tuple[str, str | None, list[dict]]:
    soup = BeautifulSoup(raw, "html.parser")
    title = _text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    effective_date = _date_from_html(soup)
    for node in soup.select("script, style, noscript, svg, nav, header, footer, aside, form, button, [role=navigation], [aria-hidden=true], .GlobalNav, .NPSNav, .Breadcrumbs, .ShareLinks"):
        node.decompose()
    for table in soup.find_all("table"):
        if "CS_Layout_Table" in table.get("class", []) or str(table.get("id", "")).startswith("cs_idLayout") or table.get("role") == "presentation":
            table.unwrap()
    content = next((soup.select_one(selector) for selector in ("main", "#MainContent", "#main", "article", "#content", "body") if soup.select_one(selector)), soup)
    blocks = []
    headings: list[tuple[int, str]] = []
    for node in content.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"]):
        if any(parent.name in ("table", "p", "li") for parent in node.parents if parent is not content):
            continue
        if node.name.startswith("h") and len(node.name) == 2:
            text = _text(node.get_text(" ", strip=True))
            level = int(node.name[1])
            headings = [(n, value) for n, value in headings if n < level]
            if text:
                headings.append((level, text))
            if node.name == "h1" and not title:
                title = text
        elif node.name == "table":
            text = _html_table(node)
        else:
            text = _text(node.get_text(" ", strip=True))
        if text:
            blocks.append({"text": text, "heading_path": " > ".join(value for _, value in headings) or title, "kind": "table" if node.name == "table" else "paragraph"})
    if not blocks:
        text = _text(content.get_text(" ", strip=True))
        if text:
            blocks.append({"text": text, "heading_path": title, "kind": "paragraph"})
    return title, effective_date, blocks


def _pdf_blocks(raw: bytes) -> tuple[str, str | None, list[dict]]:
    blocks = []
    with pdfplumber.open(BytesIO(raw)) as pdf:
        title = _text(str((pdf.metadata or {}).get("Title") or ""))
        date_match = re.search(r"D:(\d{4})(\d{2})(\d{2})", str((pdf.metadata or {}).get("CreationDate") or ""))
        effective_date = "-".join(date_match.groups()) if date_match else None
        for page_number, page in enumerate(pdf.pages, 1):
            tables = []
            for candidate in page.find_tables():
                rows = candidate.extract()
                if len(rows) >= 2 and sum(sum(bool(cell and cell.strip()) for cell in row) >= 2 for row in rows) >= 2:
                    tables.append(candidate)

            def outside_tables(obj):
                if obj.get("object_type") != "char":
                    return True
                x, y = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
                return not any(x0 <= x <= x1 and top <= y <= bottom for x0, top, x1, bottom in (table.bbox for table in tables))

            body = page.filter(outside_tables).extract_text() or ""
            if not title and body.strip():
                title = _text(body.splitlines()[0])[:240]
            heading = f"{title or 'PDF'} > PDF page {page_number}"
            for paragraph in re.split(r"\n\s*\n", body):
                text = _text(paragraph)
                if text:
                    blocks.append({"text": text, "heading_path": heading, "kind": "paragraph"})
            for table in tables:
                text = _table(table.extract())
                if text:
                    blocks.append({"text": text, "heading_path": heading, "kind": "table"})
    return title, effective_date, blocks


def ingest_document(rawbytes: bytes, url: str, crawled_at: str, content_type: str) -> dict:
    """Extract blocks with offsets into canonical normalized text; no network."""
    url = canonicalize_url(url)
    if rawbytes.lstrip().startswith(b"%PDF") or "application/pdf" in content_type.lower():
        page_type = "pdf"
        title, effective_date, blocks = _pdf_blocks(rawbytes)
    elif "html" in content_type.lower() or rawbytes.lstrip().startswith(b"<"):
        page_type = "html"
        title, effective_date, blocks = _html_blocks(rawbytes)
    else:
        raise ValueError("Unsupported public document content type")
    normalized_text = "\n\n".join(block["text"] for block in blocks)
    cursor = 0
    for block in blocks:
        block["start"] = cursor
        block["end"] = cursor + len(block["text"])
        cursor = block["end"] + 2
    if not normalized_text.strip():
        raise ValueError("Document has no selectable/extracted text")
    return {
        "doc_id": _sha(url), "source_url": url, "content_hash": _sha(normalized_text),
        "title": title or urlsplit(url).path.rsplit("/", 1)[-1], "page_type": page_type,
        "effective_date": effective_date, "crawled_at": crawled_at,
        "normalized_blocks_json": json.dumps(blocks, ensure_ascii=False),
        "normalized_text": normalized_text, "blocks": blocks,
        "has_table": any(block["kind"] == "table" for block in blocks), "raw_sha256": _sha(rawbytes),
    }


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _links(raw: bytes, url: str, config: dict) -> list[str]:
    result = set()
    for anchor in BeautifulSoup(raw, "html.parser").find_all("a", href=True):
        link = urljoin(url, anchor["href"])
        if is_allowed_url(link, config):
            result.add(canonicalize_url(link))
    return sorted(result)


class _Crawler:
    """One serial session; robots, redirects and retries share a start-rate cap."""

    def __init__(self, root: Path, config: dict):
        self.root, self.config = root, config
        self.user_agent = f"{config['crawler_user_agent']} (contact: {config['crawler_contact_email']})"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self.interval = max(1.0, 1.0 / float(config.get("requests_per_second", 1)))
        self.last_start = None
        self.request_count = 0
        self.robots: dict[str, RobotFileParser] = {}
        self.manifest_path = root / "data/raw/manifest.jsonl"
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_requests = int(config.get("max_request_attempts", 1200))

    def _save_raw(self, response, url: str, kind: str) -> dict:
        raw = response.content
        raw_hash = _sha(raw)
        content_type = response.headers.get("Content-Type", "")
        extension = "pdf" if raw.lstrip().startswith(b"%PDF") else "html" if "html" in content_type else "bin"
        path = self.root / f"data/raw/{raw_hash}.{extension}"
        if not path.exists():
            path.write_bytes(raw)
        record = {"source_url": url, "crawled_at": _utc(), "raw_sha256": raw_hash, "raw_path": str(path.relative_to(self.root)), "content_type": content_type, "http_status": response.status_code, "kind": kind, "bytes": len(raw)}
        _append_jsonl(self.manifest_path, record)
        return record

    def _request(self, url: str, kind: str):
        for attempt in range(3):
            if self.request_count >= self.max_requests:
                raise RuntimeError("request_limit")
            if self.last_start is not None:
                time.sleep(max(0.0, self.interval - (time.monotonic() - self.last_start)))
            self.last_start = time.monotonic()
            self.request_count += 1
            try:
                response = self.session.get(url, timeout=(10, 30), allow_redirects=False)
            except requests.RequestException:
                if attempt == 2:
                    raise RuntimeError("transport_failure") from None
                time.sleep(2 ** attempt)
                continue
            record = self._save_raw(response, url, kind)
            if self.request_count % 10 == 0:
                print(json.dumps({"crawl_progress": {"request_attempts": self.request_count, "last_url": url, "http_status": response.status_code}}), flush=True)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                retry_after = response.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 2 ** attempt
                time.sleep(min(max(delay, 1.0), 60.0))
                continue
            return response, record
        raise RuntimeError("transport_failure")

    def _robots_for(self, url: str) -> RobotFileParser:
        host = urlsplit(url).hostname
        if host not in self.robots:
            robots_url = f"https://{host}/robots.txt"
            parser = RobotFileParser(robots_url)
            response, _ = self._request(robots_url, "robots")
            if response.status_code == 200:
                parser.parse(response.content.decode("utf-8", errors="replace").splitlines())
                delay = parser.crawl_delay(self.user_agent)
                rate = parser.request_rate(self.user_agent)
                self.interval = max(self.interval, float(delay or 0), rate.seconds / rate.requests if rate and rate.requests else 0)
            elif response.status_code == 404:
                parser.parse(["User-agent: *", "Disallow:"])
            else:
                parser.parse(["User-agent: *", "Disallow: /"])
            self.robots[host] = parser
        return self.robots[host]

    def fetch(self, url: str):
        for _ in range(4):
            if not is_allowed_url(url, self.config):
                raise RuntimeError("outside_allowlist")
            if not self._robots_for(url).can_fetch(self.user_agent, url):
                raise RuntimeError("robots_denied")
            response, record = self._request(url, "document")
            if response.status_code in (301, 302, 303, 307, 308):
                try:
                    url = canonicalize_url(urljoin(url, response.headers.get("Location", "")))
                except ValueError:
                    raise RuntimeError("invalid_redirect") from None
                continue
            if response.status_code != 200:
                raise RuntimeError(f"http_{response.status_code}")
            if len(response.content) > int(self.config.get("max_document_bytes", 20 * 1024 * 1024)):
                raise RuntimeError("document_too_large")
            return response.content, record
        raise RuntimeError("redirect_limit")


def ingest_corpus(root: str | Path, source_config: dict, max_html: int = 150, max_pdf: int = 5) -> dict:
    """Capture a restartable qualifying corpus; fail gates before any network."""
    email = source_config.get("crawler_contact_email")
    if not email or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise IngestionGateError("A configured crawler contact email is required before fetching")
    if source_config.get("instructor_domain_approval") not in (True, "approved", "verified", "confirmed"):
        raise IngestionGateError("Confirm the required domain approval before fetching")
    rate = float(source_config.get("requests_per_second", 1))
    if rate <= 0 or rate > 1:
        raise IngestionGateError("Crawler request rate must be greater than zero and at most one per second")
    root = Path(root)
    crawler = _Crawler(root, source_config)
    document_path = root / "data/documents.jsonl"
    documents = _read_jsonl(document_path)
    if any(not is_allowed_url(doc["source_url"], source_config) for doc in documents):
        raise IngestionGateError("Saved corpus contains URLs outside the current allowlist; use a separate corpus")
    hashes = {doc["content_hash"] for doc in documents}
    by_url = {doc["source_url"]: doc for doc in documents}
    raw_records = {record["source_url"]: record for record in _read_jsonl(crawler.manifest_path) if record.get("kind") == "document" and record.get("http_status") == 200}
    frontier = deque(canonicalize_url(url) for url in source_config.get("seeds", []) if is_allowed_url(url, source_config))
    queued = set(frontier)
    visited = set()
    rejected = []
    fetched = duplicates = 0
    table_target = int(source_config.get("minimum_table_documents", 3))

    def counts():
        return {"usable_html": sum(doc["page_type"] == "html" for doc in documents), "usable_pdf": sum(doc["page_type"] == "pdf" for doc in documents), "usable_table_documents": sum(bool(doc["has_table"]) for doc in documents)}

    def complete():
        current = counts()
        return current["usable_html"] >= max_html and current["usable_pdf"] >= max_pdf and current["usable_table_documents"] >= table_target

    try:
        while frontier and not complete():
            url = frontier.popleft()
            if url in visited:
                continue
            visited.add(url)
            if urlsplit(url).path.lower().endswith(".pdf") and counts()["usable_pdf"] >= max_pdf:
                continue
            try:
                if url in raw_records:
                    record = raw_records[url]
                    raw = (root / record["raw_path"]).read_bytes()
                    if _sha(raw) != record["raw_sha256"]:
                        raise RuntimeError("saved_raw_hash_mismatch")
                else:
                    raw, record = crawler.fetch(url)
                    fetched += 1
                if "html" in record["content_type"].lower() or raw.lstrip().startswith(b"<"):
                    for link in _links(raw, record["source_url"], source_config):
                        if link not in queued:
                            queued.add(link)
                            if urlsplit(link).path.lower().endswith(".pdf"):
                                frontier.appendleft(link)
                            else:
                                frontier.append(link)
                if record["source_url"] in by_url:
                    continue
                document = ingest_document(raw, record["source_url"], record["crawled_at"], record["content_type"])
                if len(document["normalized_text"]) < int(source_config.get("minimum_text_characters", 80)):
                    raise RuntimeError("insufficient_extracted_text")
                if document["content_hash"] in hashes:
                    duplicates += 1
                    continue
                hashes.add(document["content_hash"])
                documents.append(document)
                by_url[document["source_url"]] = document
                _append_jsonl(document_path, document)
                if len(documents) % 10 == 0:
                    print(json.dumps({"crawl_progress": {"accepted_documents": len(documents), **counts(), "request_attempts": crawler.request_count}}), flush=True)
            except RuntimeError as error:
                rejected.append({"url": url, "reason": str(error)})
                if str(error) == "request_limit":
                    break
            except (ValueError, OSError, KeyError, TypeError):
                rejected.append({"url": url, "reason": "extraction_or_saved_data_failure"})
    finally:
        crawler.session.close()
    summary = {"status": "complete" if complete() else "incomplete", "captured_at_utc": _utc(), "targets": {"html": max_html, "pdf": max_pdf, "table_documents": table_target}, "counts": {**counts(), "discovered_urls": len(queued), "visited_urls": len(visited), "fetched_this_run": fetched, "request_attempts_this_run": crawler.request_count, "duplicate_documents_this_run": duplicates, "rejected_this_run": len(rejected)}, "rejections": rejected, "documents_path": str(document_path.relative_to(root)), "raw_manifest_path": str(crawler.manifest_path.relative_to(root)), "limits": {"requests_per_second": min(1.0, 1.0 / crawler.interval), "max_request_attempts": crawler.max_requests}, "crawler_contact_is_placeholder": bool(source_config.get("crawler_contact_is_placeholder")), "limitations": ["Public contact text redacted by email/phone patterns; this is not comprehensive name/PII detection", "Extracted document dates may be publication/update dates, not proof of present applicability", "PDF table extraction and sampled normalized content still require human inspection"]}
    if summary["crawler_contact_is_placeholder"]:
        summary["limitations"].append("The user explicitly selected a placeholder crawler contact; this does not satisfy the course's working-contact expectation")
    (root / "data/corpus_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
