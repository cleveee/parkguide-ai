"""Run with .venv/bin/streamlit run app.py --server.address 127.0.0.1"""
import streamlit as st

from parkguide.chat import PARK_NAMES, answer, gold_drafts_ready
from parkguide.runtime import config
from parkguide.source_links import cited_source_pages


def show_sources(trace):
    pages = cited_source_pages(trace)
    if not pages:
        return
    st.markdown("**Sources used**")
    st.caption("Official links open the current page. Saved excerpts below describe the snapshot used for this answer.")
    for number, page in enumerate(pages, 1):
        with st.container(border=True):
            st.link_button(f"{number}. {page['title']}", page["source_url"], use_container_width=True)
            st.caption(f"{page['page_type'].upper()} · Source date: {page['effective_date'] or 'unknown'} · Saved: {page['captured_label']}")
            count = len(page["passages"])
            with st.expander(f"View {count} cited passage{'s' if count != 1 else ''}"):
                for passage in page["passages"]:
                    st.text(passage["heading_path"] or page["title"])
                    st.caption("Cited for claim " + ", ".join(map(str, passage["claim_numbers"])))
                    if passage["excerpt"]:
                        st.text(("…" if passage["excerpt_leading_omission"] else "") + passage["excerpt"] + ("…" if passage["excerpt_truncated"] else ""))
                    if passage["pdf_start_page"]:
                        st.link_button(f"Open PDF at recorded starting page {passage['pdf_start_page']}", passage["passage_url"])
                    if passage["source_spans"]:
                        st.caption("Saved text offsets: " + "; ".join(f"{span['start']}–{span['end']}" for span in passage["source_spans"]))
                st.caption("Excerpts total at most 25 words per source page. Full saved passages remain in the run evidence.")

st.set_page_config(page_title="ParkGuide", page_icon="🌲")
st.title("ParkGuide")
st.caption("Choose a park to explore its saved official NPS information.")
settings = config()
if "messages" not in st.session_state:
    st.session_state.messages = []
selected_park = st.selectbox("Park", list(PARK_NAMES), index=None,
                           format_func=lambda park: f"{PARK_NAMES[park]} National Park",
                           placeholder="Choose a park", key="selected_park")
if st.session_state.get("conversation_park") != selected_park:
    st.session_state.messages = []
    st.session_state.conversation_park = selected_park
if selected_park:
    st.info(f"**Selected park: {PARK_NAMES[selected_park]} National Park**\n\nAnswers use only this park's saved NPS sources.")
    st.caption("Answers require cited, checked passages. Official links show current pages; saved sources do not verify live conditions. Ask a ranger for safety-sensitive decisions.")
else:
    st.info("Choose a park to start a conversation.")
if st.sidebar.button("New conversation", disabled=selected_park is None):
    st.session_state.messages = []
with st.sidebar.expander("Search settings"):
    mode = st.selectbox("Search", ["hybrid", "dense", "bm25"])
    rerank = st.checkbox("Rerank passages", value=settings['retrieval'].get('selected_park_rerank',True))
if not gold_drafts_ready():
    st.warning("Chat is awaiting source collection and preparation of the evaluation questions. The local application is ready for setup.")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("trace"):
            show_sources(message["trace"])
            with st.expander("Search trace and other retrieved passages"):
                trace = message["trace"]
                st.write("Search question:", trace["retrieval_query"])
                st.json({"filters": trace["filters"], "timings": trace["retrieval"].get("timings", {}), "guard_checks": trace["guard_errors"],"context_selection":trace['retrieval'].get('context_selection')})
                def trace_rows(items):
                    return [{"rank": item.get("rank"), "chunk_id": item["chunk_id"], "title": item.get("title"), "source_url": item.get("source_url"), **item.get("scores", {})} for item in items]
                st.write("Before reranking")
                st.dataframe(trace_rows(trace["retrieval"].get("candidates", [])))
                st.write("After reranking" if trace.get('rerank_enabled') else 'Final ordering (reranking disabled)')
                st.dataframe(trace_rows(trace["retrieval"].get("reranked", [])))
                if trace.get('citation_review'):
                    st.write('Source-support check (AI review)')
                    st.json(trace['citation_review'])
                if trace.get('source_derivation'):
                    st.write('Calculation from source table cells')
                    st.json(trace['source_derivation'])
                cited_ids = {passage["chunk_id"] for page in cited_source_pages(trace) for passage in page["passages"]}
                other_sources = [source for source in trace["contexts"] if source["chunk_id"] not in cited_ids]
                if other_sources:
                    st.caption("Other retrieved passages below were not cited by the delivered answer.")
                for source in other_sources:
                    st.markdown(f"[{source.get('title', 'NPS source')}]({source['source_url']})")
                    st.caption(f"Source date: {source.get('effective_date') or 'unknown'} · Captured: {source.get('crawled_at', 'unknown')}")
question = st.chat_input(f"Ask about visiting {PARK_NAMES[selected_park]}" if selected_park else "Choose a park first",
                         disabled=selected_park is None or not gold_drafts_ready())
if question:
    history = [{"role": message["role"], "content": message["content"]} for message in st.session_state.messages]
    with st.spinner("Searching official sources…"):
        try:
            result = answer(question, history, mode=mode, rerank=rerank, selected_park=selected_park)
        except RuntimeError as error:
            st.error(str(error))
            st.stop()
        except Exception:
            st.error("The model request failed. Details are retained without exposing credentials; please check local setup.")
            st.stop()
    st.session_state.messages.extend([{"role": "user", "content": question}, {"role": "assistant", "content": result["rendered"], "trace": result}])
    st.rerun()
