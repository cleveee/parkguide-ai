"""Small, source-authored follow-ups; no model call or browser-supplied evidence.

A catalog entry is eligible only while its exact supporting quote exists in a
selected-park chunk of the active build and document metadata matches its snapshot.
"""
from contextlib import closing
import json
import re
import sqlite3

from .runtime import ROOT, sqlite_uri
from .source_links import official_source_url

PARK_NAMES = {"yose": "Yosemite", "yell": "Yellowstone", "grca": "Grand Canyon"}
_STOP = set("a an the in on at of for to from with and or is are be do does can should how what which where when my i me we it its may park national yosemite yellowstone grand canyon".split())


def load_catalog():
    try:
        catalog = json.loads((ROOT / "config/followup_questions.json").read_text())
        return catalog if isinstance(catalog, list) else []
    except (OSError, ValueError):
        return []


def _terms(text):
    synonyms = {"dog": "pet", "dogs": "pet", "pets": "pet", "buses": "bus", "shuttles": "shuttle", "trails": "trail",
                "paths": "path", "animals": "animal", "bears": "bear", "wolves": "wolf", "passes": "pass"}
    return {synonyms.get(word, word) for word in re.findall(r"[a-z0-9]+", text.casefold())} - _STOP


def _normalized(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def supported_questions(db, build_id, park):
    """Return only questions with a real, bounded supporting passage; fail closed."""
    if park not in PARK_NAMES:
        return []
    catalog = [item for item in load_catalog() if isinstance(item, dict) and item.get("park") == park]
    catalog = [item for item in catalog if all(isinstance(item.get(key), str) and item[key].strip()
               for key in ("id", "question", "source_url", "supporting_quote", "topic"))
               and len(item["question"]) <= 1000 and len(item["supporting_quote"]) <= 2000
               and official_source_url(item["source_url"]) == item["source_url"]
               and item["source_url"].startswith(f"https://www.nps.gov/{park}/planyourvisit/")
               and isinstance(item.get("keywords"), list) and all(isinstance(word, str) for word in item["keywords"])]
    if not catalog:
        return []
    urls = sorted({item["source_url"] for item in catalog})
    try:
        with closing(sqlite3.connect(sqlite_uri(db), uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            build = connection.execute("SELECT manifest_json FROM index_builds WHERE build_id=? AND active=1", (build_id,)).fetchone()
            if not build:
                return []
            snapshot = json.loads(build["manifest_json"])["document_snapshot"]
            marks = ",".join("?" for _ in urls)
            rows = connection.execute(
                f"SELECT c.chunk_id,c.doc_id,c.text,c.token_count,d.source_url,d.content_hash FROM chunks c "
                f"JOIN documents d ON d.doc_id=c.doc_id WHERE c.build_id=? AND d.source_url IN ({marks}) ORDER BY c.chunk_id",
                [build_id, *urls]).fetchall()
    except (sqlite3.Error, OSError, ValueError, KeyError, TypeError):
        return []
    supported = []
    for item in catalog:
        for row in rows:
            metadata = snapshot.get(row["doc_id"], {})
            # A short single chunk is guaranteed to fit the existing 1600-token context.
            if (row["source_url"] == item["source_url"] and metadata.get("source_url") == row["source_url"]
                    and metadata.get("content_hash") == row["content_hash"] and row["token_count"] <= 1200
                    and item["supporting_quote"] in row["text"]):
                supported.append({**item, "evidence_ids": [row["chunk_id"]]})
                break
    return supported


def resolve_question(db, build_id, park, question):
    """Exact self-contained catalog questions use server-reloaded support on send."""
    return next((item for item in supported_questions(db, build_id, park)
                 if _normalized(item["question"]) == _normalized(question)), None)


def suggest_questions(db, build_id, park, question, sources, history, answer_text=""):
    asked = [item["content"] for item in history if item.get("role") == "user"] + [question]
    asked_keys = {_normalized(text) for text in asked}
    asked_terms = [_terms(text) for text in asked]
    query_terms = _terms(question + " " + answer_text)
    source_urls = {source["source_url"] for source in sources}
    candidates = supported_questions(db, build_id, park)
    # Identify the subject from the latest question, not broad shared safety pages.
    topics = {item["topic"] for item in candidates if query_terms.intersection(_terms(" ".join(item["keywords"])))}
    ranked = []
    for item in candidates:
        if _normalized(item["question"]) in asked_keys:
            continue
        terms = _terms(item["question"])
        if any(terms and len(terms & prior) / len(terms | prior) >= 0.7 for prior in asked_terms):
            continue
        shared = len(query_terms.intersection(_terms(" ".join(item["keywords"]))))
        same_source = item["source_url"] in source_urls
        if topics and item["topic"] not in topics:
            continue
        if not topics:
            continue
        score = shared * 3 + int(same_source) * 2
        ranked.append((score, item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    output, seen = [], set()
    for _, item in ranked:
        key = _normalized(item["question"])
        if key not in seen:
            seen.add(key)
            output.append({name: item[name] for name in ("id", "question", "source_url", "supporting_quote", "evidence_ids")})
        if len(output) == 3:
            break
    return output
