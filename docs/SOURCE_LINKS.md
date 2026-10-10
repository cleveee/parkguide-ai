# Source links

The chatbot now shows **Sources used** immediately below each cited answer. Each card opens the official NPS page and shows its source date and the time the snapshot was saved. Expand the card to read bounded verbatim excerpts, headings, claim numbers and saved text offsets. PDF passages also link to their recorded starting page; a chunk may extend onto a later page.

`src/parkguide/source_links.py` resolves only the final delivered response's claim `evidence_ids` against that response's saved contexts. It never derives a card URL from generated Markdown, prior assistant messages, raw withheld claims, or uncited candidates. Unknown/conflicting IDs and URLs outside the approved NPS visitor paths are excluded. Refusals, clarifications and closed-book responses have no source cards.

Repeated URLs share one card while distinct passages and their claim references are retained. Excerpts are contiguous windows from the actual saved text, with a total budget of 25 words per page shared across passages. They help inspect citations and do not prove semantic support. The full original context remains in the local run artifact. The official link opens today's page, which may differ from the captured snapshot.

The Streamlit UI and offline HTML report use the same helper. The report derives 307 page cards and 336 cited passages for 196 responses across all 305 historical attempts. Its final selected B3/dialogue subset has 32 page cards retaining 33 passages across 23 of 30 responses. Original measurements, responses and AI review labels are preserved; the readable answer text and source cards are derived display fields.

The original source-link presentation update left retrieval, generation, history and the database unchanged. The subsequent [park-selector update](PARK_SCOPE.md) changes the current UI's scope/history policy and strengthens claim review, with separate new diagnostics. Uncited retrieval remains available in **Search trace and other retrieved passages**, clearly separate from answer attribution. Historical source-link verification does not rerun the seven diagnostic stages, certify human review, or consume the held-out test.

Verification includes a fresh 126-test pass, replay of every saved attempt, verbatim/excerpt-budget checks, synthetic attribution/URL/PDF boundary checks, and offline Streamlit checks with real saved traces (one page with multiple passages, table calculation, and refusal). Live browser evidence and its separately recorded API usage are in `artifacts/ui/source-links-verification.json`; the screenshot is `artifacts/ui/source-links-preview.png`. Independent review is `artifacts/ui/source-link-review.md`.

Regenerate the HTML and JSON after updating saved evidence:

```sh
.venv/bin/python scripts/build_dashboard.py
```

The builder makes no provider calls and never rewrites the original run or review artifacts.
