"""One shared chat path for Streamlit and actual conversation evaluation."""
from datetime import datetime, timezone
from copy import deepcopy
import json
import re
import time

import tiktoken
from dotenv import load_dotenv

from .budget import Budget
from .embedding_cache import cached_embed
from .guards import render_claims, validate_answer
from .runtime import ROOT, config, digest
from .source_links import official_source_url

PARKS = {"yose": r"\byosemite\b", "yell": r"\byellowstone\b", "grca": r"\bgrand canyon\b"}
PARK_NAMES = {"yose": "Yosemite", "yell": "Yellowstone", "grca": "Grand Canyon"}
_REJECTED_GENERATION_CODES = {
    "invalid_response_schema", "invalid_claim_schema", "unknown_or_duplicate_evidence_id",
    "uncited_claim", "answer_without_claims", "claims_on_nonanswer",
    "incomplete_generation", "invalid_provider_response", "returned_model_differs_from_approved",
}
_MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
_CALENDAR = re.compile(rf"\b(?:{_MONTHS}\.?\s*(?:\d{{1,2}}(?:st|nd|rd|th)?\b)?|spring|summer|autumn|fall|winter)\b", re.I)
_YEAR = re.compile(r"\b20\d{2}(?:\s*[-–]\s*(?:20)?\d{2})?\b")
_ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")
_COMPARISON = re.compile(r"\b(?:compare|comparison|both|their|each|versus|vs|differ|difference|two)\b", re.I)


def _positive_parks(text):
    mentions = []
    for park, pattern in PARKS.items():
        for match in re.finditer(pattern, text, re.I):
            preceding = text[:match.start()]
            if not re.search(r"\b(?:not|except|excluding|rather than|instead of)\s+$", preceding, re.I):
                mentions.append((match.start(), park))
    return list(dict.fromkeys(park for _, park in sorted(mentions)))


def _follow_up(text):
    return bool(re.search(r"^(?:and\b|also\b|what about\b|how about\b|instead\b|I mean(?:t)?\b|actually\b)", text, re.I)
                or re.search(r"\b(?:it|its|that|those|there|their|them|same|these|both|each|former|latter)\b", text, re.I)
                or _COMPARISON.search(text)
                or not re.sub(r"[\s,?.!-]", "", _topic_text(text)))


def _topic_text(text):
    """Keep user subjects; park/date constraints are maintained separately."""
    text = _ISO_DATE.sub(" ", text)
    text = _NUMERIC_DATE.sub(" ", text)
    text = _CALENDAR.sub(" ", text)
    text = _YEAR.sub(" ", text)
    for pattern in PARKS.values():
        text = re.sub(pattern + r"(?:['’]s)?", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip(" ,?.")


def _context_date(text, calendar, year):
    iso = _ISO_DATE.search(text)
    numeric = _NUMERIC_DATE.search(text)
    if iso or numeric:
        try:
            match = iso or numeric
            date = datetime.strptime(match.group(0), "%Y-%m-%d" if iso else "%m/%d/%Y")
            return date.strftime("%B") + f" {date.day}", str(date.year)
        except ValueError:
            return None, None
    dates = _CALENDAR.findall(text)
    years = _YEAR.findall(text)
    return (" / ".join(dates) if dates else calendar, " / ".join(years) if years else year)


def resolve_query(question, history):
    """Carry rolling user subjects and replace explicit park/calendar slots.

    Assistant answers never become retrieval evidence. The first subject and
    three recent follow-ups bound the inherited topic without losing its anchor.
    """
    users = [message["content"] for message in history if message["role"] == "user"]
    parks, mentioned, topics = [], [], []
    calendar = year = None
    previous_topics = []
    inherit = False
    for text in [*users, question]:
        explicit = _positive_parks(text)
        comparison = bool(_COMPARISON.search(text))
        inherit = bool(topics) and _follow_up(text)
        if not inherit:
            topics, calendar, year = [], None, None
        previous_topics = list(topics)
        for park in explicit:
            mentioned = [earlier for earlier in mentioned if earlier != park] + [park]
        if explicit:
            parks = list(dict.fromkeys([*parks, *explicit])) if comparison and len(explicit) == 1 else explicit
        elif comparison and mentioned:
            parks = mentioned[-2:] if re.search(r"\b(?:both|two)\b", text, re.I) else mentioned[:]
        calendar, year = _context_date(text, calendar, year)
        topic = _topic_text(text)
        if topic:
            topics.append(topic)
        if len(topics) > 4:
            topics = [topics[0], *topics[-3:]]
    query = question
    # Negated alternatives are history constraints, not extra retrieval targets.
    for pattern in PARKS.values():
        query = re.sub(r"\b(?:not|except|excluding|rather than|instead of)\s+" + pattern, "", query, flags=re.I)
    additions = []
    if inherit and previous_topics:
        additions.append("Previous topic: " + " ".join(previous_topics))
        if re.search(r'\b(?:whenever|anytime|any time)\b', ' '.join(previous_topics), re.I) and re.search(r'\b(?:entrance|station|enter|go in)\b', question + ' ' + ' '.join(previous_topics), re.I):
            additions.append('Topic: entrance opening hours')
        if calendar or year:
            additions.append("Date: " + " ".join(value for value in (calendar, year) if value))
    if parks and additions:
        additions.append("Parks: " + ", ".join(PARK_NAMES[park] for park in parks))
    if additions:
        query += " " + " ".join(additions)
    filters = {"parks": parks} if parks else {}
    return query, filters


def gold_drafts_ready():
    manifest = ROOT / "data/evaluation/gold-draft-manifest.json"
    if not manifest.exists():
        return False
    saved = json.loads(manifest.read_text())
    drafts = ROOT / "data/evaluation/gold-drafts.jsonl"
    import hashlib
    if not drafts.exists():
        return False
    current_hash=hashlib.sha256(drafts.read_bytes()).hexdigest()
    if saved.get('count')==40 and current_hash==saved.get('sha256'):
        return True
    reviewed=ROOT/'data/evaluation/gold-reviewed-manifest.json'
    if not reviewed.exists():
        return False
    revision=json.loads(reviewed.read_text())
    rows=[json.loads(line) for line in drafts.read_text().splitlines() if line.strip()]
    return revision.get('count')==40 and revision.get('original_authoring_sha256')==saved.get('sha256') and revision.get('sha256')==current_hash and len(rows)==40 and all(row.get('verification_status')=='human_verified' and row.get('human_verifier') and row.get('verified_at') for row in rows)


def preflight_response(question, history, filters):
    """Handle visibly missing references and unavailable private lookups."""
    if re.search(r'\b(?:booking|passport|reservation)\s+[A-Z]{1,6}\d{3,}\b', question, re.I):
        return {"action": "refuse", "answer": "I cannot access private bookings, item records, or live assignments. Please contact the park's official reservation or lost-property service.", "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "private_record_lookup"}
    if re.search(r'\b(?:dose|dosage)\b',question,re.I) and re.search(r'\b(?:my|me|personal|I)\b',question,re.I):
        return {"action":"refuse","answer":"I cannot give a personal medication dose or clear you to continue hiking. Please seek a qualified medical professional; contact park emergency assistance if urgent.","claims":[],"usage":{},"elapsed_ms":0,"preflight_reason":"personal_medical_request"}
    if not history and not filters.get('parks') and len(question.split()) <= 8 and re.search(r'\b(?:it|that|there|closest)\b|\bgo in\b', question, re.I):
        return {"action": "clarify", "answer": "Which park, entrance, place, or item do you mean? If distance matters, please give your starting location.", "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "missing_reference"}
    return None


def scoped_preflight(question, selected_park):
    """Keep an explicit UI scope and unavailable live/private lookups local."""
    name = PARK_NAMES[selected_park]
    if any(park != selected_park for park in _positive_parks(question)):
        return {"action": "refuse", "answer": f"This conversation is for {name} National Park. Choose another park in the selector to ask about it.",
                "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "selected_park_mismatch"}
    if re.search(r"\b(?:right now|today|tonight|currently|real[- ]time|live availability|this week|current (?:weather|conditions|closures|availability|vacancies|price))\b", question, re.I):
        return {"action": "refuse", "answer": f"I cannot verify live conditions, availability, or current updates for {name} from the saved database. Please check the park's official information.",
                "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "live_information_unavailable"}
    if (re.search(r"\b(?:my|our)\s+(?:(?:private|personal)\s+)?(?:reservation|booking|permit|passport)\b", question, re.I)
            and re.search(r"\b(?:look\s*up|retrieve|check|find|confirm|status|number|assigned|assignment)\b", question, re.I)):
        return {"action": "refuse", "answer": "The saved public-source database contains no personal reservation or permit records. Please use the official reservation service.",
                "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "private_record_lookup"}
    return None


def sources_within_park(trace, selected_park):
    """Fail closed even if a retriever returns an unexpected candidate."""
    seen = {}
    for field in ("candidates", "reranked", "final"):
        for source in trace.get(field, []):
            url = official_source_url(source.get("source_url"))
            if (not url or not url.startswith(f"https://www.nps.gov/{selected_park}/planyourvisit/")
                    or not isinstance(source.get("chunk_id"), str) or not source["chunk_id"]
                    or not isinstance(source.get("text"), str) or not source["text"].strip()):
                return False
            identity = (url, source["text"], source.get("doc_id"), source.get("content_hash"))
            if source["chunk_id"] in seen and seen[source["chunk_id"]] != identity:
                return False
            seen[source["chunk_id"]] = identity
    return True


def table_followup_filters(question, history, filters, db):
    """Resolve explicit table requests and follow-ups to stored table pages.

    Previous assistant text supplies only a URL hint. It is never fact evidence,
    and unknown URLs or pages outside the current park scope are discarded.
    """
    users=[item['content'] for item in history if item['role']=='user']
    table_request=bool(re.search(r'\btable\b',question,re.I) or (_follow_up(question) and any(re.search(r'\btable\b',text,re.I) for text in users[-3:])))
    if not table_request or (re.search(r'\bPDF\b',question,re.I)):
        return filters
    urls = {url for item in history if item['role']=='assistant' for url in re.findall(r'\]\((https://www\.nps\.gov/[^)\s]+)\)',item['content'])}
    from .store import load_documents
    parks=filters.get('parks',[])
    tables=[doc['source_url'] for doc in load_documents(db) if doc.get('has_table') and (not parks or doc['source_url'].split('/')[3] in parks)]
    known=[url for url in tables if url in urls]
    chosen=known or tables
    return {**filters,'source_url':sorted(chosen)} if chosen else filters


def _retry_delay(error, attempt):
    """Respect bounded Azure backoff; never retry a long hint prematurely."""
    hint = getattr(error, 'retry_after_seconds', None)
    if isinstance(hint, (int, float)) and not isinstance(hint, bool) and hint >= 0:
        return max(1, hint) if hint <= 60 else None
    return 60 if getattr(error, 'status_code', None) == 429 else min(2 ** attempt, 4)


def paid_claim_review(question, claims, contexts, history, settings):
    from .claim_review import review_claims
    budget=Budget()
    upper=len(json.dumps([question,claims,contexts,history]).encode())+12000
    for attempt in range(settings['evaluation']['transient_retries']+1):
        reservation=budget.reserve('generation',upper,1000)
        try:
            review=review_claims(question,claims,contexts,history)
        except Exception as error:
            usage=getattr(error,'usage',None)
            budget.settle(reservation,usage.get('input_tokens') if usage else None,usage.get('output_tokens',0) if usage else 0,error=True)
            retryable=getattr(error,'status_code',None) in (429,500,502,503,504) or getattr(error,'code','')=='provider_transport_error'
            delay = _retry_delay(error, attempt)
            if not retryable or attempt>=settings['evaluation']['transient_retries'] or delay is None:
                raise
            time.sleep(delay)
            continue
        review['cost_estimate_usd']=budget.settle(reservation,review['usage']['input_tokens'],review['usage']['output_tokens'])
        return review


def answer(question, history=None, *, mode="hybrid", build_id=None, rerank=None,
           generator=None, embedder=None, retriever=None, reviewer=None, closed_book=False, enforce_gate=True,
           selected_park=None):
    started = time.perf_counter()
    if selected_park is not None and (not isinstance(selected_park, str) or selected_park not in PARK_NAMES):
        raise ValueError("Select one supported park: yose, yell, or grca")
    if selected_park is not None and closed_book:
        raise ValueError("A selected-park conversation must use database evidence")
    load_dotenv(ROOT / ".env", override=False)
    # Keep each saved trace limited to what actually preceded this request.
    # Evaluation and the UI append later turns to their own mutable history.
    history = deepcopy(history or [])
    history_scope_reset = bool(selected_park and any(
        park != selected_park for message in history for park in _positive_parks(message["content"])))
    if history_scope_reset:
        history = []
    settings = config()
    default_generator=generator is None
    if rerank is None:
        rerank = settings['retrieval'].get('selected_park_rerank', True) if selected_park else settings['retrieval'].get('default_rerank',True)
    if enforce_gate and not gold_drafts_ready():
        raise RuntimeError("Author and freeze all 40 source-based gold drafts before live chatbot answers")
    retrieval_query, filters = resolve_query(question, history)
    generation_question = question
    if selected_park:
        filters = {**filters, "parks": [selected_park]}
        # The metadata filter enforces scope. Add only the name for meaning;
        # repeating generic 'park' terms can bury a specific visitor subject.
        if selected_park not in _positive_parks(retrieval_query):
            retrieval_query = f"{PARK_NAMES[selected_park]}: {retrieval_query}"
        generation_question = f"Selected park: {PARK_NAMES[selected_park]} National Park. Answer only for this park from its saved passages.\nVisitor question: {question}"
    preflight = scoped_preflight(question, selected_park) if selected_park else None
    if retriever is None and not closed_book and preflight is None:
        filters = table_followup_filters(question, history, filters, ROOT / settings['database'])
    if preflight is None and not closed_book:
        preflight = preflight_response(question, history, filters)
    if retriever is None:
        from .retrieval import retrieve
        retriever = retrieve
    trace = {"candidates": [], "final": [], "timings": {}, "candidate_count": 0}
    if not closed_book and preflight is None:
        vector = None if mode == "bm25" else (embedder or cached_embed)([retrieval_query])[0]
        trace = retriever(ROOT / settings["database"], retrieval_query, vector,
                          mode=mode, build_id=build_id, filters=filters, rerank=rerank)
    scope_errors = []
    if selected_park and not sources_within_park(trace, selected_park):
        scope_errors.append("selected_park_source_scope_violation")
        preflight = {"action": "refuse", "answer": "I could not verify that the retrieved evidence belongs to the selected park. Please check the official source.",
                     "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "invalid_selected_park_sources"}
    context_order = trace['final']
    if filters.get('source_url'):
        from .table_math import select_named_table_rows
        named=select_named_table_rows(trace['candidates'],[item['content'] for item in history if item['role']=='user']+[question])
        identifiers={row['chunk_id'] for row in named}
        preferred=[item for item in trace['candidates'] if item['chunk_id'] in identifiers]
        context_order=(preferred+[item for item in context_order if item['chunk_id'] not in identifiers])[:settings['retrieval']['final_context_count']]
        trace['context_selection']={'method':'named_table_rows_then_original_final','named_rows':sorted({row['row_label'] for row in named}),'selected_ids':[item['chunk_id'] for item in context_order],'ranking_unchanged':True}
    encoding = tiktoken.get_encoding("cl100k_base")
    contexts, used = [], 0
    for item in ([] if scope_errors else context_order):
        tokens = len(encoding.encode(item["text"]))
        if used + tokens <= settings["retrieval"]["context_token_budget"]:
            contexts.append(item)
            used += tokens
    budget = None
    reservation = None
    if preflight is not None:
        payload = preflight
    elif not closed_book and not contexts:
        payload = {"action": "refuse", "answer": "I cannot answer from the available NPS source snapshot. Please consult the park's official information or a ranger.", "claims": [], "usage": {}, "elapsed_ms": 0}
    else:
        if generator is None:
            from .generation import generate
            generator = generate
            budget = Budget()
            input_upper = len(json.dumps([question, contexts, history]).encode()) + 12000
            reservation = budget.reserve("generation", input_upper, settings["generation"]["max_output_tokens"])
        for attempt in range(settings["evaluation"]["transient_retries"] + 1):
            try:
                payload = generator(generation_question, contexts, history, closed_book=closed_book)
                break
            except Exception as error:
                error_cost = 0
                if budget:
                    usage = getattr(error, "usage", None)
                    error_cost = budget.settle(reservation, usage.get("input_tokens") if usage else None, usage.get("output_tokens", 0) if usage else 0, error=True)
                if selected_park and getattr(error, "code", None) in _REJECTED_GENERATION_CODES:
                    payload = {"action": "refuse", "answer": "", "claims": [],
                               "usage": getattr(error, "usage", None) or {},
                               "cost_estimate_usd": error_cost,
                               "elapsed_ms": getattr(error, "elapsed_ms", None),
                               "generation_error": {"code": error.code}}
                    reservation = None  # The failed response was already settled.
                    break
                retryable = getattr(error, "status_code", None) in (429, 500, 502, 503, 504) or getattr(error, "code", "") in ("connection_error", "timeout", "provider_transport_error")
                delay = _retry_delay(error, attempt)
                if not retryable or attempt >= settings["evaluation"]["transient_retries"] or delay is None:
                    raise
                time.sleep(delay)
                if budget:
                    reservation = budget.reserve("generation", input_upper, settings["generation"]["max_output_tokens"])
        if budget and reservation:
            usage = payload["usage"]
            payload["cost_estimate_usd"] = budget.settle(reservation, usage["input_tokens"], usage["output_tokens"])
    original = deepcopy(payload)
    derivation = None
    if not closed_book and preflight is None and contexts and not payload.get('generation_error'):
        from .table_math import derive_table_difference
        computed=derive_table_difference(question,history,contexts)
        if computed:
            derivation=computed['trace']
            payload={**payload,'action':'answer','claims':[computed['claim']],'answer':computed['claim']['text']}
    review_trace=None
    if selected_park and payload['action'] == 'answer' and not default_generator and reviewer is None:
        review_trace = {"error": {"type": "ValueError", "message": "selected_park_requires_source_review"}}
        payload = {**payload, 'action': 'refuse', 'claims': [], 'answer': "I could not validate the source support for this answer. Please check the official information."}
    if not closed_book and payload['action']=='answer' and (reviewer is not None or (default_generator and (selected_park or settings['generation'].get('review_claims',False)))):
        try:
            review_trace=reviewer(generation_question,payload['claims'],contexts,history) if reviewer else paid_claim_review(generation_question,payload['claims'],contexts,history,settings)
            if selected_park:
                from .claim_review import validate_review_decisions
                review_trace['decisions'] = validate_review_decisions(review_trace['decisions'], payload['claims'], contexts)
            retained=[claim for claim,decision in zip(payload['claims'],review_trace['decisions']) if decision['supported']]
            review_trace['withheld_claims']=len(payload['claims'])-len(retained)
            cost=payload.get('cost_estimate_usd',0)+review_trace.get('cost_estimate_usd',0)
            payload={**payload,'claims':retained,'cost_estimate_usd':cost,'answer':' '.join(claim['text'] for claim in retained)} if retained else {**payload,'action':'refuse','claims':[],'cost_estimate_usd':cost,'answer':"I could not substantiate this answer from the selected NPS passages. Please check the official source or ask a ranger."}
        except Exception as error:
            review_trace={'error':{'type':type(error).__name__,'message':str(error) if isinstance(error,(RuntimeError,ValueError)) else 'Claim review failed; sensitive details suppressed'}}
            if getattr(error, 'review_diagnostics', None):
                review_trace['error']['diagnostics'] = error.review_diagnostics
            payload={**payload,'action':'refuse','claims':[],'answer':"I could not validate the source support for this answer. Please check the official information or ask a ranger."}
    # Free-form model refusal/clarification prose is not reviewed factual output.
    # A selected-park UI must not deliver an uncited fact via that field either.
    if selected_park and preflight is None and payload['action'] != 'answer':
        message = (f"I could not find enough supporting information in the saved {PARK_NAMES[selected_park]} sources to answer that. Please check the official NPS information."
                   if payload['action'] == 'refuse' else
                   f"Which place, date, or detail in {PARK_NAMES[selected_park]} National Park do you mean?")
        payload = {**payload, 'answer': message, 'claims': []}
    source_texts = None
    if not closed_book and contexts and retriever.__module__ == "parkguide.retrieval":
        from .store import load_documents
        wanted = {item["doc_id"] for item in contexts}
        source_texts = {item["doc_id"]: item["normalized_text"] for item in load_documents(ROOT / settings["database"]) if item["doc_id"] in wanted}
    errors = [] if closed_book else validate_answer(payload, contexts, source_texts,question)
    errors += scope_errors
    if selected_park and any(park != selected_park for claim in payload.get('claims', []) for park in _positive_parks(claim['text'])):
        errors.append("claim_outside_selected_park")
    if errors:
        payload = {**payload, "action": "refuse", "answer": "I could not validate the answer's citations or quotations. Please check the official NPS sources or ask a ranger.", "claims": []}
    rendered = payload.get("answer", "") if closed_book else render_claims(payload, contexts)
    result = {"question": question, "history": history, "history_scope_reset": history_scope_reset,
              "selected_park": selected_park, "generation_question": generation_question,
              "retrieval_query": retrieval_query, "closed_book": closed_book, "rerank_enabled": rerank,
              "filters": filters, "retrieval": trace, "contexts": contexts,
              "response": payload, "raw_response": original, "rendered": rendered,
              "citation_review": review_trace,
              "source_derivation": derivation,
              "guard_errors": errors, "config_hash": digest(settings),
              "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
              "timestamp": datetime.now(timezone.utc).isoformat()}
    return result
