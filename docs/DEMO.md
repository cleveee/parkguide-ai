# Local classroom demo: 8–10 minutes

Present the local ParkGuide PoC using saved official NPS sources. Formal course evaluation and human gold verification remain pending. Use the current Azure-only model and park selector; historical seven-stage results describe the older generator.

## Prepare

Run `.venv/bin/parkguide doctor` from the repository and open `http://127.0.0.1:8511`. If needed, start Streamlit using README instructions. Choose Yosemite in **Park**. Confirm the selected banner and park-specific input. Keep hybrid retrieval and the selected-park reranker enabled; the legacy diagnostic default remains off. All chat generation and claim review use `gpt-6-luna` on the same Azure endpoint/key as embeddings.

Open the [HTML dashboard](../dashboard/index.html), [status](STATUS.md), and [park-scope evidence](PARK_SCOPE.md). Saved results are a replay, not a new live request. Each new model call uses the remaining approved budget.

## Walkthrough

| Time | Action | Explain |
| --- | --- | --- |
| 0–1 min | Show the empty selector, choose Yosemite, and point to the banner. | One park per conversation; changing parks clears history. Local Python/SQLite/NumPy/BM25/Streamlit, one Azure resource, no deployment. |
| 1–2 min | Open corpus and build counts in the report. | 150 HTML pages, five PDFs, 45 table-bearing documents; raw bytes, dates, source hashes and saved vectors are inspectable. |
| 2–4 min | Ask the two Yosemite bear questions below. Expand **Sources used** and search trace. | Actual prior messages resolve the follow-up, but retrieved saved text supplies evidence. Official links open current pages; excerpts show the snapshot used. |
| 4–5 min | Ask about a fictional tour, then a live-road condition. | A missing fact and a live lookup must be withheld. Refusal does not prove a real-world place is absent. |
| 5–6 min | Ask a Yellowstone question while Yosemite is selected, then select Yellowstone. | The prompt cannot silently change scope. The selector starts a fresh conversation for the new park. |
| 6–8 min | Show all scoped iterations and the original seven stages. | Distinguish operational action/scope matches, AI support proposals and human accuracy. Retain failures and provider-rate-limit reservations. Selected reranking was enabled after a real scoped retrieval miss. |
| 8–10 min | Show remaining human work and an actual recorded failure. | Forty gold drafts need verification, the 24/16 split/test is unconsumed, and final development acceptance must pin the current configuration. No agent certifies human review. |

## Live prompts

With Yosemite selected:

1. “What distance should I keep from a bear outside developed areas?”
2. “What should I do if that bear is in a developed area?”
3. “What are the submarine tour departure times at Blue Lantern Lagoon?”
4. “Are all park roads open right now?”
5. “Now answer for Yellowstone: what distance should I keep from bears?”

Then select Yellowstone and ask “How far should I stay from bears?” Show that Yosemite messages were cleared. A private lookup example is “Please look up my private reservation and confirm its status.”

These are non-gold diagnostics. Inspect actual outputs; do not promise a particular answer or repeat a request until a preferred response appears. Over-refusal and unsupported acceptance remain possible despite exact witnesses. Safety-sensitive decisions need current official information or a ranger.

The original selected B3/reranker comparison used the older generator and no-rerank default; keep its manifest settings intact. Current park-scope checks use Azure Luna, source-only review and the selected-park reranker, so they are not a single-factor comparison to that historical stage. Costs are token-based list estimates, not billing. The repo remains local with no commits, remote, push, deployment or submission.
