"""Display attribution from delivered claims and their saved context, without networking."""
from collections import defaultdict
from datetime import datetime
import re
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo


def official_source_url(value):
    """Accept only the official source host and visitor paths used by this corpus."""
    if not isinstance(value, str):
        return None
    if any(character.isspace() or ord(character) < 32 for character in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme != "https" or parsed.netloc.lower() != "www.nps.gov":
        return None
    if not any(parsed.path.startswith(f"/{park}/planyourvisit/") for park in ("yose", "yell", "grca")):
        return None
    path = unquote(parsed.path)
    if any(part in (".", "..") for part in path.split("/")) or parsed.query:
        return None
    if any(character in path for character in ('\\', '"', "'", '<', '>', '`', '\x7f')) or any(ord(character) < 32 for character in path):
        return None
    return f"https://www.nps.gov{parsed.path}"


def captured_label(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return value
        return stamp.astimezone(ZoneInfo("America/Chicago")).strftime("%b %d, %Y, %I:%M %p %Z")
    except (ValueError, AttributeError, TypeError):
        return "Unknown"


def cited_source_pages(trace):
    """Deduplicate pages, retaining each cited passage and its delivered claim numbers.

    Retrieved-but-uncited contexts and withheld/raw claims cannot become answer
    sources. Conflicting duplicate context IDs fail closed for that identifier.
    """
    payload = trace.get("response", {})
    if trace.get("closed_book") or payload.get("action") != "answer":
        return []
    by_id = defaultdict(list)
    for context in trace.get("contexts", []):
        if context.get("chunk_id"):
            by_id[context["chunk_id"]].append(context)
    pages = {}
    for number, claim in enumerate(payload.get("claims", []), 1):
        for identifier in dict.fromkeys(claim.get("evidence_ids", [])):
            matches = by_id.get(identifier, [])
            if not matches or any(context != matches[0] for context in matches[1:]):
                continue
            source = matches[0]
            url = official_source_url(source.get("source_url"))
            if not url:
                continue
            page = pages.setdefault(url, {
                "source_url": url, "title": source.get("title") or "Official NPS source",
                "page_type": source.get("page_type", "unknown"),
                "effective_date": source.get("effective_date"), "crawled_at": source.get("crawled_at"),
                "captured_label": captured_label(source.get("crawled_at")), "passages": [],
            })
            passage = next((item for item in page["passages"] if item["chunk_id"] == identifier), None)
            if passage is None:
                heading = source.get("heading_path") or ""
                pdf_page = re.search(r"(?:^| > )PDF page ([1-9]\d*)(?:$| > )", heading)
                start_page = int(pdf_page[1]) if pdf_page and source.get("page_type") == "pdf" else None
                passage = {
                    "chunk_id": identifier, "doc_id": source.get("doc_id"),
                    "heading_path": heading, "text": source.get("text", ""),
                    "source_spans": source.get("source_spans", source.get("source_span", [])),
                    "content_hash": source.get("content_hash"), "claim_numbers": [],
                    "pdf_start_page": start_page,
                    "passage_url": url + (f"#page={start_page}" if start_page else ""),
                }
                page["passages"].append(passage)
            if number not in passage["claim_numbers"]:
                passage["claim_numbers"].append(number)
    # Distribute a maximum 25-word excerpt budget across every cited passage
    # from the same page. Select a verbatim window matching delivered claim
    # words, without generating additional prose or treating it as entailment.
    for page in pages.values():
        count_passages = len(page["passages"])
        for position, passage in enumerate(page["passages"]):
            allocation = 25 // count_passages + (position < 25 % count_passages)
            text = passage["text"]
            if text.startswith("Heading:") and "\n\n" in text:
                text = text.split("\n\n", 1)[1]
            words = list(re.finditer(r"\w+", text))
            count = min(allocation, len(words))
            claim_words = set(re.findall(r"\w+", " ".join(payload["claims"][index - 1]["text"] for index in passage["claim_numbers"]).lower()))
            claim_words -= {"the", "a", "an", "and", "or", "of", "to", "is", "in", "from", "at", "for", "as", "on", "be", "are", "with", "by", "this", "that", "it", "have", "can", "not"}
            def score(start):
                matches = {word.group().lower() for word in words[start:start + count]} & claim_words
                return sum(2 if word.isdigit() else 1 for word in matches)
            start = max(range(len(words) - count + 1), key=score) if count else 0
            passage["excerpt"] = text[words[start].start():words[start + count - 1].end()] if count else ""
            passage["excerpt_leading_omission"] = start > 0
            passage["excerpt_truncated"] = start + count < len(words)
    return list(pages.values())
