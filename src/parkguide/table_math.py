"""Fail-closed subtraction of named rows in immutable Markdown table chunks."""
from decimal import Decimal, InvalidOperation
import json
import re


_UNIT_ALIASES = {
    "mi": ("mi", "mile", "miles"), "km": ("km", "kilometer", "kilometers", "kilometre", "kilometres"),
    "ft": ("ft", "foot", "feet"), "m": ("m", "meter", "meters", "metre", "metres"),
    "yards": ("yd", "yds", "yard", "yards"), "USD": ("usd", "dollar", "dollars"),
}
_CANONICAL_UNITS = {alias: unit for unit, aliases in _UNIT_ALIASES.items() for alias in aliases}


def _cells(line):
    return [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def _tables(contexts):
    tables = []
    for context in contexts:
        if not context.get("chunk_id") or not context.get("doc_id"):
            continue
        spans = context.get("source_span", context.get("source_spans", context.get("source_span_json", [])))
        if isinstance(spans, str):
            try:
                spans = json.loads(spans)
            except (TypeError, ValueError):
                continue
        if isinstance(spans, dict):
            spans = spans.get("spans", [spans])
        headers = [span for span in spans if span.get("kind") == "table_header"]
        lines, cursor, number = context.get("text", "").splitlines(), 0, 0
        while cursor + 1 < len(lines):
            first, second = lines[cursor].strip(), lines[cursor + 1].strip()
            if not (first.startswith("|") and first.endswith("|") and second.startswith("|") and second.endswith("|")):
                cursor += 1
                continue
            header, separator = _cells(first), _cells(second)
            if len(header) != len(separator) or not all(re.fullmatch(r":?-{2,}:?", cell) for cell in separator):
                cursor += 1
                continue
            identity = (headers[number].get("start"), headers[number].get("end")) if number < len(headers) else (context["chunk_id"], number)
            key = (context["doc_id"], context.get("content_hash"), identity, tuple(header))
            cursor += 2
            while cursor < len(lines) and lines[cursor].strip().startswith("|") and lines[cursor].strip().endswith("|"):
                cells = _cells(lines[cursor])
                if len(cells) == len(header) and cells[0] and re.search(r"[A-Za-z]", cells[0]):
                    tables.append({"table_key": key, "header": header, "cells": cells, "row_label": cells[0],
                                   "row_text": lines[cursor], "chunk_id": context["chunk_id"],
                                   "doc_id": context["doc_id"], "source_spans": spans})
                cursor += 1
            number += 1
    return tables


def _mentions(text, labels):
    matches = []
    for label in labels:
        terms = re.findall(r"\w+", label)
        pattern = r"(?<!\w)" + r"\W+".join(map(re.escape, terms)) + r"(?!\w)"
        flags = 0 if len(label) == 1 else re.I
        matches.extend((match.start(), match.end(), label) for match in re.finditer(pattern, text, flags))
    matches = [item for item in matches if not any(other[0] <= item[0] and other[1] >= item[1] and other[1] - other[0] > item[1] - item[0] for other in matches)]
    return list(dict.fromkeys(label for _, _, label in sorted(matches)))


def select_named_table_rows(contexts, user_texts):
    """Return witnessed rows named in the most recent explicit user text.

    This selects source rows, never modifies ranking or creates context/chunk IDs.
    The caller must explicitly trace any later context-packing change.
    """
    rows = _tables(contexts)
    labels = {row["row_label"] for row in rows}
    for text in reversed(user_texts):
        names = _mentions(text, labels)
        if names:
            return [row for row in rows if row["row_label"] in names]
    return []


def _unit_column(question, header):
    requested = {unit for unit, aliases in _UNIT_ALIASES.items() if any(re.search(r"\b" + re.escape(alias) + r"\b", question, re.I) for alias in aliases)}
    elevation = bool(re.search(r"\b(?:elevation|altitude|higher|lower|height)\b", question, re.I))
    distance = bool(re.search(r"\b(?:distance|farther|further|length|longer|shorter)\b|from the rim", question, re.I))
    if elevation and distance:
        return None
    candidates = []
    for index, column in enumerate(header[1:], 1):
        match = re.search(r"\(([^()]+)\)", column)
        if not match:
            continue
        unit_names = [part.strip().lower() for part in match.group(1).split("/")]
        if any(unit not in _CANONICAL_UNITS for unit in unit_names):
            continue
        units = [_CANONICAL_UNITS[unit] for unit in unit_names]
        name = column[:match.start()].strip()
        if elevation and not re.search(r"elevation|altitude|height", name, re.I):
            continue
        if distance and not re.search(r"distance|length", name, re.I):
            continue
        positions = [position for position, unit in enumerate(units) if unit in requested]
        if requested and len(positions) != 1:
            continue
        candidates.append((index, name, units, positions[0] if positions else 0))
    return candidates[0] if len(candidates) == 1 else None


def _quantities(cell, units):
    parts = cell.split("/")
    if len(parts) != len(units) or any(not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", part.strip()) for part in parts):
        return None
    try:
        return [Decimal(part.strip()) for part in parts]
    except InvalidOperation:
        return None


def _decimal(value):
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def derive_table_difference(question, history, contexts):
    """Return {claim, trace} for a fully witnessed difference, otherwise None."""
    if not re.search(r"how much (?:farther|further|higher|lower)|\bdifference\b|how many (?:more|less|fewer)", question, re.I):
        return None
    rows = _tables(contexts)
    labels = {row["row_label"] for row in rows}
    names = _mentions(question, labels)
    if len(names) == 1 and re.search(r"\b(?:that|it|spot|previous|former|latter)\b", question, re.I):
        for message in reversed(history or []):
            if message.get("role") != "user" or message.get("content") == question:
                continue
            earlier = [name for name in _mentions(message["content"], labels) if name not in names]
            if earlier:
                if len(earlier) != 1:
                    return None
                names += earlier
                break
    if len(names) != 2:
        return None
    more = bool(re.search(r"\b(?:farther|further|higher|more)\b", question, re.I))
    less = bool(re.search(r"\b(?:lower|less|fewer)\b", question, re.I))
    if more and less:
        return None
    if more or less:
        relation = re.search(r"\bthan\b|\bcompared (?:to|with)\b", question, re.I)
        if relation is None or _mentions(question[:relation.start()], labels) != [names[0]]:
            return None
        after = question[relation.end():]
        references = _mentions(after, labels)
        if references != [names[1]] and (references or not re.search(r"\b(?:that|it|spot|previous|former|latter)\b", after, re.I)):
            return None
    candidates, witnessed = {}, {name: set() for name in names}
    for row in rows:
        if row["row_label"] not in names:
            continue
        column = _unit_column(question, row["header"])
        if column is None:
            continue
        index, column_name, units, position = column
        values = _quantities(row["cells"][index], units)
        if values is None:
            return None
        witnessed[row["row_label"]].add((tuple(units), tuple(values)))
        group = candidates.setdefault((row["table_key"], index, position), {})
        group.setdefault(row["row_label"], []).append((row, values, column))
    if any(len(values) != 1 for values in witnessed.values()):
        return None
    complete = [group for group in candidates.values() if all(name in group for name in names)]
    if len(complete) != 1:
        return None
    group = complete[0]
    first, second = group[names[0]][0], group[names[1]][0]
    index, column_name, units, position = first[2]
    a, b = first[1][position], second[1][position]
    left, right = (b, a) if less else (a, b)
    result = left - right
    if (more or less) and result < 0:
        return None
    absolute = not more and not less
    if absolute:
        left, right = max(a, b), min(a, b)
        result = left - right
    equation = f"{_decimal(left)} - {_decimal(right)}"
    equation += f" = {_decimal(result)} {units[position]}"
    ids = list(dict.fromkeys([first[0]["chunk_id"], second[0]["chunk_id"]]))
    text = f"The {'absolute ' if absolute else ''}difference in {column_name} between {names[0]} and {names[1]} is {_decimal(result)} {units[position]} ({equation})."
    operands = [{"row_label": row["row_label"], "source_cell": row["cells"][index], "value": _decimal(values[position]),
                 "chunk_id": row["chunk_id"], "source_spans": row["source_spans"]} for row, values, _ in (first, second)]
    return {"claim": {"text": text, "evidence_ids": ids}, "trace": {
        "operation": "absolute_difference" if absolute else "second_minus_first" if less else "first_minus_second",
        "column": first[0]["header"][index], "unit": units[position], "column_units": units,
        "unit_role": "primary" if position == 0 else "paired", "operands": operands,
        "result": _decimal(result), "equation": equation,
    }}
