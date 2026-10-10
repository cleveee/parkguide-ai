"""Deterministic citation, numerical-witness, and quotation checks."""
import re
from decimal import Decimal

NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
UNIT = r'(?:ft|feet|foot|mi|miles?|km|m|meters?|metres?|yards?|dollars?)'
UNIT_CANONICAL = {'ft':'ft','feet':'ft','foot':'ft','mi':'mi','mile':'mi','miles':'mi','km':'km','m':'m','meter':'m','meters':'m','metre':'m','metres':'m','yard':'yd','yards':'yd','dollar':'usd','dollars':'usd'}


def canonical_units(*units):
    return {UNIT_CANONICAL[unit.lower()] for unit in units if unit}


def calculations(text):
    expression = rf'({NUMBER})\s*({UNIT})?\s*([+−-])\s*({NUMBER})\s*({UNIT})?\s*=\s*({NUMBER})\s*({UNIT})?'
    return re.findall(expression,text,re.I)


def numeric_values(text):
    # PDF text commonly joins a value to its unit (1120ft). Recognize only
    # known units, not digits embedded in identifiers such as ZX9401.
    boundary = rf'(?=$|[^\w.]|{UNIT}\b)'
    return {Decimal(value.replace(',', '')) for value in re.findall(r'(?<![\w.])(' + NUMBER + ')' + boundary, text, re.I)}


def verified_calculations(text, support):
    """Accept explicit addition/subtraction equations only with cited operands.

    This proves arithmetic and witnesses, not the meaning or units of operands.
    Semantic review must still check that the cited table columns are appropriate.
    """
    witnessed = numeric_values(support)
    derived = set()
    for left, unit_a, operation, right, unit_b, result, unit_c in calculations(text):
        a, b, c = (Decimal(value.replace(',', '')) for value in (left, right, result))
        calculated = a + b if operation == '+' else a - b
        units = canonical_units(unit_a,unit_b,unit_c)
        if a in witnessed and b in witnessed and calculated == c and len(units)<=1:
            derived.add(c)
    return derived


def words(text):
    return re.findall(r"\w+", text.lower())


def longest_shared_phrase(answer, source):
    left, right = words(answer), words(source)
    previous = [0] * (len(right) + 1)
    longest = 0
    for word in left:
        current = [0] * (len(right) + 1)
        for position, source_word in enumerate(right, 1):
            if word == source_word:
                current[position] = previous[position - 1] + 1
                longest = max(longest, current[position])
        previous = current
    return longest


def validate_answer(payload, contexts, source_texts=None, question=None):
    errors = []
    sources = {item["chunk_id"]: item for item in contexts}
    if payload.get("action") not in ("answer", "clarify", "refuse"):
        errors.append("invalid_action")
    claims = payload.get("claims", [])
    if payload.get("action") == "answer" and not claims:
        errors.append("missing_claim_citations")
    if payload.get("action") != "answer" and claims:
        errors.append("nonanswer_contains_factual_claims")
    for claim in claims:
        if re.search(r"https?://", claim.get("text", "")):
            errors.append("model_written_url")
        identifiers = claim.get("evidence_ids", [])
        if not identifiers or any(identifier not in sources for identifier in identifiers):
            errors.append("unknown_or_missing_citation")
            continue
        support = "\n".join(sources[identifier]["text"] for identifier in identifiers)
        # This checks numerical witnesses; it is not a semantic entailment proof.
        checked_text=claim.get('text','')
        # A repeated requested calendar date is an input constraint, not a new
        # source fact. Exempt the complete date phrase, never unrelated numbers.
        if question:
            date_pattern=r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+20\d{2})?\b'
            for date in re.findall(date_pattern,question,re.I):
                checked_text=re.sub(re.escape(date), '', checked_text,flags=re.I)
        numbers = numeric_values(checked_text)
        allowed = numeric_values(support) | verified_calculations(claim.get("text", ""), support)
        if not numbers <= allowed:
            errors.append("number_without_source_witness")
        for left, unit_a, operation, right, unit_b, result, unit_c in calculations(claim.get('text','')):
            a,b,c=(Decimal(value.replace(',','')) for value in (left,right,result))
            if (a+b if operation=='+' else a-b)!=c or len(canonical_units(unit_a,unit_b,unit_c))>1:
                errors.append('invalid_calculation')
    text = "\n".join(claim.get("text", "") for claim in claims)
    pages = dict(source_texts or {})
    if not pages:
        for source in contexts:
            page = source.get("doc_id", source.get("source_url", source["chunk_id"]))
            pages[page] = pages.get(page, "") + "\n" + source["text"]
    for page_text in pages.values():
        if longest_shared_phrase(text, page_text) > 25:
            errors.append("quote_limit")
    return sorted(set(errors))


def render_claims(payload, contexts):
    sources = {item["chunk_id"]: item for item in contexts}
    if payload.get("action") != "answer":
        return payload.get("answer", "I do not have sufficient evidence in this source snapshot.")
    lines = []
    for claim in payload.get("claims", []):
        links = []
        for identifier in claim["evidence_ids"]:
            source = sources[identifier]
            title = source.get("title", "NPS source").replace("[", "").replace("]", "")
            links.append(f"[{title}]({source['source_url']})")
        lines.append(claim["text"] + " " + " ".join(dict.fromkeys(links)))
    return "\n\n".join(lines)
