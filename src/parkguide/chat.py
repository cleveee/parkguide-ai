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
from .dialogue import explanation_request, detail_request

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
_WRITTEN_DATE = re.compile(rf"\b({_MONTHS})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*(20\d{{2}})\b", re.I)
_RELATIVE_DATE = re.compile(r"\b(?:today|tonight|tomorrow|yesterday|right now|this (?:week|weekend)|next (?:week|weekend))\b", re.I)
_COMPARISON = re.compile(r"\b(?:compare|comparison|both|their|each|versus|vs|differ|difference|two)\b", re.I)
_PLACE = re.compile(r"\b([a-z][a-z'’-]*)\s+(?:falls?|springs?|lake|creek|river|valley|village|point|meadow|loop|trail|road)\b", re.I)
_PLACE_NON_NAMES = {"a", "an", "the", "in", "during", "this", "next", "last", "for", "until", "after", "before", "through", "early", "late", "and", "or", "about"}


def _place_spans(text):
    """Preserve names such as Yosemite Fall and May Lake during slot removal."""
    return [match.span() for match in _PLACE.finditer(text) if match.group(1).lower() not in _PLACE_NON_NAMES]


def _outside_places(match, spans):
    return not any(match.start() < end and match.end() > start for start, end in spans)


def _positive_parks(text):
    mentions = []
    for park, pattern in PARKS.items():
        for match in re.finditer(pattern, text, re.I):
            preceding = text[:match.start()]
            if not re.search(r"\b(?:not|except|excluding|rather than|instead of)\s+$", preceding, re.I):
                mentions.append((match.start(), park))
    return list(dict.fromkeys(park for _, park in sorted(mentions)))


def _follow_up(text):
    # Existential "there" introduces a subject; it does not refer to the last one.
    references = re.sub(r"\b(?:is|are|was|were|be|been)\s+there\b", "", text, flags=re.I)
    return bool(explanation_request(text)
                or re.search(r"^(?:and\b|also\b|what about\b|how about\b|instead\b|I mean(?:t)?\b|actually\b)", text, re.I)
                or re.search(r"\b(?:it|its|that|those|there|they|their|them|he|him|his|she|her|hers|same|these|both|each|former|latter|instead)\b", references, re.I)
                or _COMPARISON.search(text)
                or not re.sub(r"[\s,?.!-]", "", _topic_text(text)))


def _topic_text(text):
    """Keep user subjects; park/date constraints are maintained separately."""
    text = _ISO_DATE.sub(" ", text)
    text = _NUMERIC_DATE.sub(" ", text)
    text = _RELATIVE_DATE.sub(" ", text)
    places = _place_spans(text)
    text = _CALENDAR.sub(lambda match: " " if _outside_places(match, places) else match.group(), text)
    text = _YEAR.sub(" ", text)
    for pattern in PARKS.values():
        places = _place_spans(text)
        text = re.sub(pattern + r"(?:['’]s)?", lambda match: " " if _outside_places(match, places) else match.group(), text, flags=re.I)
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
    relative = _RELATIVE_DATE.search(text)
    if relative:
        return relative.group(), None
    places = _place_spans(text)
    dates = [match.group() for match in _CALENDAR.finditer(text) if _outside_places(match, places)]
    years = _YEAR.findall(text)
    return (" / ".join(dates) if dates else calendar, " / ".join(years) if years else year)


def resolve_query(question, history):
    """Carry rolling user subjects and replace explicit park/calendar slots.

    Assistant answers never become retrieval evidence. The first subject and
    three recent follow-ups bound the inherited topic without losing its anchor.
    """
    users = []
    clarification = False
    for message in history:
        if message["role"] == "assistant":
            clarification = bool(re.match(r"^(?:which|where|what|when)\b.*\?", message["content"], re.I | re.S))
        elif message["role"] == "user":
            users.append((message["content"], clarification))
            clarification = False
    parks, mentioned, topics = [], [], []
    calendar = year = None
    previous_topics = []
    inherit = False
    for text, answers_clarification in [*users, (question, clarification)]:
        explicit = _positive_parks(text)
        comparison = bool(_COMPARISON.search(text))
        short_reply = answers_clarification and len(text.split()) <= 12 and not re.search(r"\?|^(?:can|could|do|does|is|are|what|where|when|how|why|tell)\b", text, re.I)
        inherit = bool(topics) and (_follow_up(text) or short_reply)
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
        # Confusion is a request about the existing subject, not a new subject.
        topic = "" if explanation_request(text) else _topic_text(text)
        if topic:
            topics.append(topic)
        if len(topics) > 4:
            topics = [topics[0], *topics[-3:]]
    explaining = explanation_request(question) and bool(previous_topics)
    query = " ".join(previous_topics) if explaining else question
    # Negated alternatives are history constraints, not extra retrieval targets.
    for pattern in PARKS.values():
        query = re.sub(r"\b(?:not|except|excluding|rather than|instead of)\s+" + pattern, "", query, flags=re.I)
    additions = []
    if inherit and previous_topics:
        if not explaining:
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
    if not any(message["role"] == "user" for message in history):
        parks = filters.get("parks", [])
        location = f" in {PARK_NAMES[parks[0]]} National Park" if len(parks) == 1 else ""
        text = question.strip().rstrip("?.!")
        message = None
        if explanation_request(question):
            message = "Which answer or topic would you like me to explain?"
        elif re.fullmatch(r"how (?:long|much time) (?:(?:does|will|would) (?:it|that|this|the (?:hike|walk|drive|trip)) take|is (?:it|that|this|the (?:hike|walk|drive|trip)))", text, re.I):
            message = f"Which trail, drive, or activity{location} do you mean?"
        elif re.search(r"\b(?:closest|nearest)\b", text, re.I) and (
                not re.search(r"\b(?:to|from|near|at|in)\s+\w", _topic_text(text), re.I)
                or re.search(r"\b(?:to|from|near)\s+(?:me|us|here)\b", text, re.I)):
            message = f"What is your starting location or reference point{location}?"
        elif re.fullmatch(r"(?:(?:can|may) I (?:bring|take|use) (?:it|that|this|them|those)|(?:is|are) (?:it|that|this|they|those) (?:open|allowed|permitted|safe|accessible|available)|where (?:is|are) (?:it|that|this|they|those))", text, re.I):
            message = f"Which place or item{location} do you mean?"
        if message:
            return {"action": "clarify", "answer": message, "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "missing_reference"}
    if not history and not filters.get('parks') and len(question.split()) <= 8 and re.search(r'\b(?:it|that|there|closest)\b|\bgo in\b', question, re.I):
        return {"action": "clarify", "answer": "Which park, entrance, place, or item do you mean? If distance matters, please give your starting location.", "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "missing_reference"}
    return None


def _future_status_request(question):
    """Recognize explicit future dates without rejecting historical lookups."""
    if (not re.search(r"\b(?:will|confirm|definitely|guarantee)\b", question, re.I)
            or not re.search(r"\b(?:open|reopen|closed|conditions?)\b", question, re.I)):
        return False
    today = datetime.now(timezone.utc).date()
    years = [int(year) for year in re.findall(r"\b(20\d{2})\b", question)]
    if any(year > today.year for year in years):
        return True
    if today.year not in years:
        return False
    dates = [(match.group(), "%Y-%m-%d") for match in _ISO_DATE.finditer(question)]
    dates += [(match.group(), "%m/%d/%Y") for match in _NUMERIC_DATE.finditer(question)]
    dates += [(f"{match[1][:3]} {match[2]} {match[3]}", "%b %d %Y") for match in _WRITTEN_DATE.finditer(question)]
    for text, format in dates:
        try:
            if datetime.strptime(text, format).date() > today:
                return True
        except ValueError:
            continue
    return False


def scoped_preflight(question, selected_park, resolved_question=None):
    """Keep an explicit UI scope and unavailable live/private lookups local."""
    name = PARK_NAMES[selected_park]
    if any(park != selected_park for park in _positive_parks(question)):
        return {"action": "refuse", "answer": f"This conversation is for {name} National Park. Choose another park in the selector to ask about it.",
                "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "selected_park_mismatch"}
    if _future_status_request(question):
        return {"action": "refuse", "answer": f"I cannot confirm opening status or conditions for your requested travel date from the saved {name} sources. Check the park's official updates for that date and confirm with the park before traveling.",
                "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "dated_information_unavailable"}
    live_time = re.search(r"\b(?:right now|today|tonight|tomorrow|currently|at the moment|this (?:week|weekend)|current|latest)\b", question, re.I)
    date_reply = re.sub(r"^(?:and|what about|how about)\b", "", question, flags=re.I).strip()
    live_question = resolved_question if resolved_question and not _topic_text(date_reply) else question
    live_state = re.search(r"\b(?:open|opening|closed|closures?|weather|forecast|conditions?|availability|available|vacancies|vacancy|price|prices|fees?|costs?|hours|traffic|delays?|crowds?|busy|wait|alerts?|updates?|temperature|snow|ice|flood|wildfire|smoke|safe|unsafe|passable|accessible|operating|running|sold out|fire restrictions)\b", live_question, re.I)
    visit_permission = re.search(r"\b(?:can|could|may|should) (?:I|we) (?:visit|enter|hike|camp|drive|swim|go)\b", live_question, re.I)
    if (re.search(r"\b(?:real[- ]time|live (?:availability|conditions|weather|updates?|status))\b", question, re.I)
            or live_time and (live_state or visit_permission)):
        return {"action": "refuse", "answer": f"I cannot verify live conditions, availability, or current updates for {name} from the saved database. Please check the park's official information.",
                "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "live_information_unavailable"}
    # Facility names can sit between ownership and the record ("my Bridge Bay
    # reservation"). Do not cross a verb into a general question about rules.
    if (re.search(r"\b(?:my|our)\s+(?:(?!(?:needs?|requires?|have|has|is|are|can|could|should|will|would|does|do)\b)[\w'’-]+\s+){0,6}(?:reservation|booking|permit|passport)\b", question, re.I)
            and re.search(r"\b(?:look\s*up|retrieve|check|find|confirm|status|number|assigned|assignment|paid|payment)\b", question, re.I)):
        return {"action": "refuse", "answer": "The saved public-source database contains no personal reservation or permit records. For a booking or payment check, use your booking provider's official website or contact its reservation service.",
                "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "private_record_lookup"}
    return None


def scoped_history(history, selected_park):
    """Drop foreign-park exchanges without losing earlier selected-park context."""
    retained = []
    keep_turn = True
    for message in history:
        foreign = any(park != selected_park for park in _positive_parks(message["content"]))
        if message["role"] == "user":
            keep_turn = not foreign
        if keep_turn and not foreign:
            retained.append(message)
    return retained


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


def paid_claim_review(question, claims, contexts, history, settings, *, citation_contract=None):
    from .claim_review import review_claims
    budget=Budget()
    upper=len(json.dumps([question,claims,contexts,history]).encode())+12000
    for attempt in range(settings['evaluation']['transient_retries']+1):
        reservation=budget.reserve('generation',upper,1000)
        try:
            options = {"citation_contract": citation_contract} if citation_contract is not None else {}
            review=review_claims(question,claims,contexts,history,**options)
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


def paid_dialogue_plan(question, history, selected_park, settings):
    from .dialogue import plan_dialogue
    budget = Budget()
    upper = len(json.dumps([question, history]).encode()) + 6000
    # The optional language decision gets one short attempt. Local resolution
    # handles a failure, without adding a retry chain before the answer call.
    reservation = budget.reserve('generation', upper, settings['generation']['max_output_tokens'])
    try:
        plan = plan_dialogue(question, history, selected_park)
    except Exception as error:
        usage = getattr(error, 'usage', None)
        cost = budget.settle(reservation, usage.get('input_tokens') if usage else None,
                             usage.get('output_tokens', 0) if usage else 0, error=True)
        error.cost_estimate_usd = cost
        raise
    plan['cost_estimate_usd'] = budget.settle(reservation, plan['usage']['input_tokens'], plan['usage']['output_tokens'])
    return plan


def answer(question, history=None, *, mode="hybrid", build_id=None, rerank=None,
           generator=None, embedder=None, retriever=None, reviewer=None, closed_book=False, enforce_gate=True,
           selected_park=None, planner=None):
    started = time.perf_counter()
    if selected_park is not None and (not isinstance(selected_park, str) or selected_park not in PARK_NAMES):
        raise ValueError("Select one supported park: yose, yell, or grca")
    if selected_park is not None and closed_book:
        raise ValueError("A selected-park conversation must use database evidence")
    load_dotenv(ROOT / ".env", override=False)
    # Keep each saved trace limited to what actually preceded this request.
    # Evaluation and the UI append later turns to their own mutable history.
    history = deepcopy(history or [])
    in_scope_history = scoped_history(history, selected_park) if selected_park else history
    history_scope_reset = in_scope_history != history
    history = in_scope_history
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
    preflight = scoped_preflight(question, selected_park, retrieval_query) if selected_park else None
    if retriever is None and not closed_book and preflight is None:
        filters = table_followup_filters(question, history, filters, ROOT / settings['database'])
    if preflight is None and not closed_book:
        preflight = preflight_response(question, history, filters)
    lexical_query = retrieval_query
    dialogue = {"action": "explain_previous" if history and explanation_request(question) and not detail_request(question) else
               "search_followup" if history and detail_request(question) or "Previous topic:" in retrieval_query else "search_new",
               "method": "local", "cost_estimate_usd": 0}
    if history and not closed_book and preflight is None and (planner or default_generator and selected_park):
        from .dialogue import validate_plan, clarification
        try:
            planned = planner(question, history, selected_park) if planner else paid_dialogue_plan(question, history, selected_park, settings)
            checked = validate_plan({key: planned[key] for key in ("action", "search_query", "clarification_kind")})
            # A planner cannot alter the visitor's selected park through a query.
            if selected_park and any(park != selected_park for park in _positive_parks(checked['search_query'])):
                from .generation import GenerationError
                raise GenerationError("dialogue_query_outside_selected_park", usage=planned.get('usage'))
            dialogue = {**planned, **checked, "method": "model"}
            if checked['action'].startswith('search'):
                retrieval_query = checked['search_query']
                generation_question += f"\nConversation-resolved visitor question (context only, not evidence): {retrieval_query}"
                if selected_park and selected_park not in _positive_parks(retrieval_query):
                    retrieval_query = f"{PARK_NAMES[selected_park]}: {retrieval_query}"
            elif checked['action'] == 'clarify':
                preflight = {"action": "clarify", "answer": clarification(checked['clarification_kind'], PARK_NAMES.get(selected_park, "the park")),
                             "claims": [], "usage": {}, "elapsed_ms": 0, "preflight_reason": "dialogue_clarification"}
        except Exception as error:
            # Provider/schema errors have safe codes; budget/configuration
            # RuntimeErrors remain hard limits and must never be bypassed.
            if isinstance(error, RuntimeError) and not getattr(error, 'code', None):
                raise
            dialogue = {**dialogue, "method": "local_fallback", "error": getattr(error, 'code', 'dialogue_plan_failed'),
                        "usage": getattr(error, 'usage', None) or {},
                        "cost_estimate_usd": getattr(error, 'cost_estimate_usd', 0)}
    if dialogue['action'] == 'explain_previous':
        generation_question += "\nExplain the previous answer in simpler everyday language using the supplied sources. Keep its subject, qualifiers and exceptions; do not ask the visitor to repeat the topic. When a rule has an exception, the rule sentence itself must say generally or most. Put each distinct fact in a separate claim of at most 18 words."
    elif detail_request(question):
        generation_question += "\nThe visitor requests additional detail about the same subject. Add relevant conditions or permitted examples explicitly supported by the supplied passages, beyond merely repeating the last answer. Preserve qualifiers and exceptions. Never invent reasons or details absent from these sources."
    if retriever is None:
        from .retrieval import retrieve
        retriever = retrieve
    trace = {"candidates": [], "final": [], "timings": {}, "candidate_count": 0}
    if not closed_book and preflight is None:
        if dialogue['action'] == 'explain_previous' and retriever.__module__ == 'parkguide.retrieval':
            from .dialogue import previous_evidence_ids
            from .retrieval import saved_evidence
            reused = saved_evidence(ROOT / settings['database'], previous_evidence_ids(history), build_id=build_id, filters=filters)
            if reused:
                trace = reused
        if not trace.get('evidence_reuse'):
            vector = None if mode == "bm25" else (embedder or cached_embed)([retrieval_query])[0]
            options = {'lexical_query': lexical_query} if dialogue['action'] == 'search_followup' and retriever.__module__ == 'parkguide.retrieval' else {}
            trace = retriever(ROOT / settings["database"], retrieval_query, vector,
                              mode=mode, build_id=build_id, filters=filters, rerank=rerank, **options)
    dialogue['reused_evidence_ids'] = [item['chunk_id'] for item in trace['final']] if trace.get('evidence_reuse') else []
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
            from .claim_review import STRICT_CITATION_CONTRACT, WITNESS_SELECTION_CONTRACT, select_reviewed_citations, validate_review_decisions
            requested_contract = WITNESS_SELECTION_CONTRACT if selected_park else STRICT_CITATION_CONTRACT
            review_trace=reviewer(generation_question,payload['claims'],contexts,history) if reviewer else paid_claim_review(generation_question,payload['claims'],contexts,history,settings,citation_contract=requested_contract)
            contract = review_trace.get('citation_contract', STRICT_CITATION_CONTRACT)
            reviewed_claims = payload['claims']
            if contract == WITNESS_SELECTION_CONTRACT:
                selection = select_reviewed_citations(review_trace['decisions'], payload['claims'], contexts)
                review_trace['decisions'] = selection['decisions']
                review_trace['citation_selections'] = selection['citation_selections']
                reviewed_claims = selection['claims']
            elif contract != STRICT_CITATION_CONTRACT:
                raise ValueError('invalid_citation_contract')
            elif selected_park:
                review_trace['decisions'] = validate_review_decisions(review_trace['decisions'], payload['claims'], contexts)
            retained=[claim for claim,decision in zip(reviewed_claims,review_trace['decisions']) if decision['supported']]
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
              "dialogue": dialogue,
              "source_derivation": derivation,
              "guard_errors": errors, "config_hash": digest(settings),
              "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
              "timestamp": datetime.now(timezone.utc).isoformat()}
    return result
