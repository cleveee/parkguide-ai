"""Deterministic token-bounded chunks with original character-span provenance."""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right

import numpy as np
import tiktoken

ENCODING = tiktoken.get_encoding("cl100k_base")
CHUNKER_VERSION = "parkguide-chunks-v1"


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def unpack_document(doc):
    """Support fresh ingestion dictionaries and rows loaded from SQLite."""
    result = dict(doc)
    bundle = result.get("normalized_blocks_json", "[]")
    if isinstance(bundle, str):
        bundle = json.loads(bundle)
    if isinstance(bundle, dict):
        for key, value in bundle.items():
            result.setdefault(key, value)
        blocks = bundle.get("blocks", [])
    else:
        blocks = bundle
    result.setdefault("blocks", blocks)
    result.setdefault("normalized_text", "\n\n".join(block["text"] for block in result["blocks"]))
    cursor = 0
    normalized = result["normalized_text"]
    rebuilt = []
    for source in result["blocks"]:
        block = dict(source)
        if "start" not in block or "end" not in block:
            start = normalized.find(block["text"], cursor)
            if start < 0:
                raise ValueError("Block text is absent from normalized source")
            block.update(start=start, end=start + len(block["text"]))
        if normalized[block["start"]:block["end"]] != block["text"]:
            raise ValueError("Block offsets do not match normalized source")
        if block["start"] < cursor:
            raise ValueError("Source blocks overlap or are out of order")
        cursor = block["end"]
        rebuilt.append(block)
    result["blocks"] = rebuilt
    return result


def _heading(value):
    return " > ".join(str(item) for item in value) if isinstance(value, list) else str(value or "")


def _prefix(heading):
    return f"Heading: {heading}\n\n" if heading else ""


def _windows(text, prefix, target, overlap):
    """Yield original-text slices; token offsets preserve multibyte characters."""
    if len(ENCODING.encode(prefix)) >= target - 4:
        raise ValueError("Heading/table header exceeds chunk budget; increase the target explicitly")
    tokens = ENCODING.encode(text)
    if not tokens:
        return
    decoded, offsets = ENCODING.decode_with_offsets(tokens)
    if decoded != text:
        raise ValueError("Tokenizer failed lossless source reconstruction")
    boundaries = sorted(set(offsets + [len(text)]))
    position = 0
    while position < len(text):
        start_idx = bisect_right(boundaries, position) - 1
        low, high = start_idx + 1, len(boundaries) - 1
        best = None
        while low <= high:
            middle = (low + high) // 2
            end = boundaries[middle]
            count = len(ENCODING.encode(prefix + text[position:end]))
            if count <= target:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if best is None:
            raise ValueError("A source character cannot fit the chunk budget")
        end = boundaries[best]
        yield position, end, prefix + text[position:end]
        if end == len(text):
            break
        # Find a token-boundary suffix no larger than the requested overlap.
        next_start = end
        for candidate in reversed(boundaries[start_idx + 1:best]):
            if len(ENCODING.encode(text[candidate:end])) > overlap:
                break
            next_start = candidate
        position = max(boundaries[start_idx + 1], next_start)


def _chunk(doc, strategy, target, overlap, text, spans, heading):
    config = {"strategy": strategy, "target": target, "overlap": overlap, "tokenizer": "cl100k_base", "version": CHUNKER_VERSION}
    token_count = len(ENCODING.encode(text))
    if not 0 < token_count <= target:
        raise ValueError("Chunk exceeds token budget")
    identity = {"doc_id": doc["doc_id"], "content_hash": doc["content_hash"], "config": config, "spans": spans, "text": text}
    return {
        "chunk_id": canonical_hash(identity), "doc_id": doc["doc_id"], "text": text,
        "heading_path": heading, "source_span_json": json.dumps(spans, sort_keys=True),
        "source_spans": spans, "token_count": token_count,
    }


def fixed_chunks(doc, target=200, overlap=40):
    doc = unpack_document(doc)
    text = doc["normalized_text"]
    if not text.strip():
        return []
    chunks, cursor = [], 0
    while cursor < len(text):
        block = next((b for b in doc["blocks"] if b["end"] > cursor), {})
        heading = _heading(block.get("heading_path", ""))
        start, end, body = next(_windows(text[cursor:], _prefix(heading), target, overlap))
        absolute_end = cursor + end
        spans = [{"start": max(cursor, b["start"]), "end": min(absolute_end, b["end"]), "kind": b.get("kind", "paragraph")} for b in doc["blocks"] if b["end"] > cursor and b["start"] < absolute_end]
        chunks.append(_chunk(doc, "fixed", target, overlap, body, spans, heading))
        if absolute_end == len(text):
            break
        _, offsets = ENCODING.decode_with_offsets(ENCODING.encode(text[cursor:absolute_end]))
        suffixes = sorted(set(offsets + [absolute_end - cursor]))
        next_start = absolute_end
        for offset in reversed(suffixes[1:-1]):
            candidate = cursor + offset
            if len(ENCODING.encode(text[candidate:absolute_end])) > overlap:
                break
            next_start = candidate
        cursor = max(cursor + 1, next_start)
    return chunks


def structure_chunks(doc, target=200, overlap=40):
    doc = unpack_document(doc)
    chunks, pending, pending_spans, pending_heading = [], [], [], ""

    def flush():
        nonlocal pending, pending_spans, pending_heading
        if pending:
            text = _prefix(pending_heading) + "\n\n".join(pending)
            chunks.append(_chunk(doc, "structure", target, overlap, text, pending_spans, pending_heading))
        pending, pending_spans, pending_heading = [], [], ""

    for block in doc["blocks"]:
        heading = _heading(block.get("heading_path", ""))
        text, kind = block["text"], block.get("kind", "paragraph")
        if not text.strip():
            continue
        prefix = _prefix(heading)
        span = {"start": block["start"], "end": block["end"], "kind": kind}
        if kind == "table":
            flush()
            lines = text.splitlines(keepends=True)
            if len(lines) >= 2 and set(lines[1].strip()) <= set("|:- \t"):
                header = "".join(lines[:2])
                header_span = {"start": block["start"], "end": block["start"] + len(header), "kind": "table_header"}
                offset = len(header)
                rows, row_spans = [], []

                def flush_rows():
                    nonlocal rows, row_spans
                    if rows:
                        chunks.append(_chunk(doc, "structure", target, overlap, prefix + header + "".join(rows), [header_span] + row_spans, heading))
                    rows, row_spans = [], []

                for row in lines[2:]:
                    row_span = {"start": block["start"] + offset, "end": block["start"] + offset + len(row), "kind": "table_row"}
                    offset += len(row)
                    if len(ENCODING.encode(prefix + header + "".join(rows) + row)) > target:
                        flush_rows()
                    if len(ENCODING.encode(prefix + header + row)) <= target:
                        rows.append(row)
                        row_spans.append(row_span)
                    else:
                        for start, end, segment in _windows(row, prefix + header, target, overlap):
                            spans = [header_span, {"start": row_span["start"] + start, "end": row_span["start"] + end, "kind": "table_row_fragment"}]
                            chunks.append(_chunk(doc, "structure", target, overlap, segment, spans, heading))
                flush_rows()
                if len(lines) == 2:
                    chunks.append(_chunk(doc, "structure", target, overlap, prefix + header, [header_span], heading))
                continue
        assembled = prefix + "\n\n".join(pending + [text])
        if pending and (heading != pending_heading or len(ENCODING.encode(assembled)) > target):
            flush()
        if len(ENCODING.encode(prefix + text)) <= target:
            pending_heading = heading
            pending.append(text)
            pending_spans.append(span)
        else:
            flush()
            for start, end, segment in _windows(text, prefix, target, overlap):
                spans = [{"start": block["start"] + start, "end": block["start"] + end, "kind": kind}]
                chunks.append(_chunk(doc, "structure", target, overlap, segment, spans, heading))
    flush()
    return chunks


def chunk_documents(docs, strategy="fixed", target=200, overlap=40):
    if strategy not in {"fixed", "structure"}:
        raise ValueError("Strategy must be fixed or structure")
    if target < 8 or not 0 <= overlap < target:
        raise ValueError("Require target >= 8 and 0 <= overlap < target")
    builder = fixed_chunks if strategy == "fixed" else structure_chunks
    chunks = [chunk for doc in sorted(docs, key=lambda d: d["doc_id"]) for chunk in builder(doc, target, overlap)]
    if len({chunk["chunk_id"] for chunk in chunks}) != len(chunks):
        raise ValueError("Duplicate deterministic chunks; check duplicate input documents")
    return chunks


def chunk_statistics(chunks):
    values = np.array([chunk["token_count"] for chunk in chunks], dtype=int)
    return {"chunk_count": len(chunks), "document_count": len({c["doc_id"] for c in chunks}), "tokens": int(values.sum()), "minimum": int(values.min()) if values.size else 0, "maximum": int(values.max()) if values.size else 0, "mean": float(values.mean()) if values.size else 0, "p50": float(np.percentile(values, 50)) if values.size else 0, "p95": float(np.percentile(values, 95)) if values.size else 0}
