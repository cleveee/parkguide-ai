"""Read-only source previews; original page scripts never run in the application."""
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Comment
import requests

from .source_links import official_source_url


_ALLOWED = set("div section article p h1 h2 h3 h4 h5 h6 ul ol li table thead tbody tfoot tr th td caption strong b em i u s br hr blockquote pre code span dl dt dd figure figcaption a".split())
_REMOVE = "script,style,noscript,svg,math,iframe,object,embed,link,meta,base,nav,header,footer,aside,form,button,input,textarea,select,img,video,audio,source,[hidden]:not([hidden=until-found]),[aria-hidden=true],.GlobalNav,.NPSNav,.Breadcrumbs,.ShareLinks,.ParkFooter,.modal"


class PreviewUnavailable(ValueError):
    pass


_PAGE_TAGS = _ALLOWED | set("html head title body main header footer nav aside img picture source link style button details summary time address small sup sub label".split())
_PAGE_ATTRS = set("class id title alt role width height colspan rowspan dir lang hidden style media type".split())
_ASSET_HOSTS = {"www.nps.gov", "fonts.googleapis.com", "fonts.gstatic.com"}
_PAGE_CSP = ("default-src 'none'; script-src 'none'; style-src 'unsafe-inline' https://www.nps.gov https://fonts.googleapis.com; "
             "img-src https://www.nps.gov data:; font-src https://www.nps.gov https://fonts.gstatic.com; "
             "base-uri https://www.nps.gov; form-action 'none'; connect-src 'none'")


def _page_url(value, source_url, *, asset=False):
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlsplit(urljoin(source_url, value))
        valid = parsed.scheme == "https" and not parsed.username and not parsed.password and parsed.port in (None, 443)
    except ValueError:
        return None
    if not valid:
        return None
    if asset and parsed.hostname not in _ASSET_HOSTS:
        return None
    return parsed.geturl()


def website_html(raw: bytes, source_url: str) -> str:
    """Preserve NPS layout, CSS and images in a script-free controlled document."""
    source_url = official_source_url(source_url)
    if source_url is None:
        raise PreviewUnavailable("This source is not an approved official NPS page.")
    soup = BeautifulSoup(raw, "html.parser")
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for node in list(soup.select("script,noscript,iframe,object,embed,base,meta,form,svg,math,template")):
        if node.parent is not None:
            node.decompose()
    for node in list(soup.find_all(True)):
        if node.parent is None:
            continue
        if node.name not in _PAGE_TAGS:
            node.unwrap()
            continue
        original = dict(node.attrs)
        node.attrs = {name: value for name, value in original.items()
                      if name in _PAGE_ATTRS or name.startswith("aria-")}
        if node.name == "link":
            href = _page_url(original.get("href"), source_url, asset=True)
            if "stylesheet" not in original.get("rel", []) or not href:
                node.decompose()
                continue
            node.attrs.update(href=href, rel="stylesheet")
        elif node.name == "a":
            href = _page_url(original.get("href"), source_url)
            if href:
                node.attrs.update(href=href, target="_blank", rel="noopener noreferrer")
        elif node.name in ("img", "source"):
            src = _page_url(original.get("src"), source_url, asset=True)
            if src:
                node["src"] = src
            sources = []
            for entry in str(original.get("srcset", "")).split(","):
                parts = entry.strip().split()
                if parts and (url := _page_url(parts[0], source_url, asset=True)):
                    descriptor = parts[1] if len(parts) == 2 and re.fullmatch(r"\d+(?:\.\d+)?[wx]", parts[1]) else ""
                    sources.append((url + " " + descriptor).strip())
            if sources:
                node["srcset"] = ", ".join(sources)
        elif node.name == "button":
            node["type"] = "button"
    # Build a fresh shell so no remote policy, base URL or document attributes
    # can alter the sandbox. Stylesheets and image URLs remain original assets.
    head = soup.head
    body = soup.body
    head_html = "".join(str(child) for child in head.children) if head else ""
    body_html = "".join(str(child) for child in body.children) if body else str(soup)
    body_attrs = "" if not body else "".join(' ' + name + '="' + escape(" ".join(value) if isinstance(value, list) else str(value), quote=True) + '"' for name, value in body.attrs.items())
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="' + escape(_PAGE_CSP, quote=True) + '">'
            '<base href="' + escape(source_url, quote=True) + '">' + head_html + '</head><body' + body_attrs + '>' + body_html + '</body></html>')


def live_website(source_url: str) -> str:
    """Fetch one known official HTML page, without redirects or credentials."""
    url = official_source_url(source_url)
    if url is None:
        raise PreviewUnavailable("This source is not an approved official NPS page.")
    try:
        with requests.get(url, timeout=(3, 8), stream=True, allow_redirects=False,
                          auth=lambda request: request,  # Never pick up .netrc credentials.
                          headers={"User-Agent": "ParkGuide source preview", "Accept": "text/html"}) as response:
            if response.status_code != 200 or "text/html" not in response.headers.get("Content-Type", "").lower():
                raise PreviewUnavailable("The live official page could not be loaded. Open the official page directly, or use Saved evidence.")
            parts, size = [], 0
            for part in response.iter_content(chunk_size=64 * 1024):
                size += len(part)
                if size > 2 * 1024 * 1024:
                    raise PreviewUnavailable("The live page is too large for the inline preview. Open the official page directly.")
                parts.append(part)
            return website_html(b"".join(parts), url)
    except requests.RequestException:
        raise PreviewUnavailable("The live official page could not be loaded. Try again, or use Saved evidence.") from None


def readable_html(raw: bytes) -> str:
    """Keep source text, headings, lists and tables, using our reader styling.

    No source attributes, scripts, images, forms or external resources survive.
    Construct allowed elements into a fresh tree rather than trusting attributes.
    """
    soup = BeautifulSoup(raw, "html.parser")
    # NPS's findable accordion panels contain indexed evidence. Their hidden
    # attribute is removed with all other source attributes below, exposing text.
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for node in list(soup.select(_REMOVE)):
        if node.parent is not None:
            node.decompose()
    content = next((soup.select_one(selector) for selector in ("main", "#MainContent", "#main", "article", "#content", "body") if soup.select_one(selector)), soup)
    for node in list(content.find_all(True)):
        if node.parent is None:
            continue
        # NPS's presentation tables are layout wrappers, not source data tables.
        layout = node.name == "table" and ("CS_Layout_Table" in node.get("class", []) or str(node.get("id", "")).startswith("cs_idLayout") or node.get("role") == "presentation")
        if node.name not in _ALLOWED or layout:
            node.unwrap()
            continue
        spans = {key: str(node.get(key)) for key in ("colspan", "rowspan") if node.name in ("td", "th") and re.fullmatch(r"[1-9]\d?", str(node.get(key, "")))}
        node.attrs = spans
    # The selected root can itself carry source attributes (for example onclick).
    return "".join(str(child) for child in content.children)


def source_preview(root, document: dict, bundle: dict, view="reader") -> dict:
    metadata = {key: document.get(key) for key in ("doc_id", "source_url", "title", "page_type", "crawled_at")}
    if document.get("page_type") == "pdf":
        # Preserve the distinction between the PDF and its saved extraction.
        blocks = bundle.get("blocks", [])
        body = "".join("<section><h2>" + escape(block.get("heading_path", "")) + "</h2><pre>" + escape(block.get("text", "")) + "</pre></section>" for block in blocks)
        return {**metadata, "mode": "pdf_text", "html": body}
    if view == "website":
        return {**metadata, "mode": "html_page", "html": live_website(document.get("source_url")),
                "loaded_at": datetime.now(timezone.utc).isoformat(), "content_origin": "live"}
    digest = bundle.get("raw_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise PreviewUnavailable("The original saved page is unavailable.")
    path = root / "data" / "raw" / (digest + ".html")
    if not path.is_file():
        raise PreviewUnavailable("The original saved page is not included in this runtime.")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise PreviewUnavailable("The saved page did not match its recorded checksum.")
    return {**metadata, "mode": "html_reader", "html": readable_html(raw)}
