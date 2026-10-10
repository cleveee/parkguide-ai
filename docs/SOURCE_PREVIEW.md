# Source page preview

Source cards offer a green **Open source** button with a scan icon at the top
right; the saved-evidence dialog offers **Preview source**. The preview
fetches the live NPS page's HTML and retains its
original layout, stylesheets, inline styling and images. Exact review quotes are
marked directly inside that full-page preview and scrolled into view. Collapsed
sections containing matching text are revealed. The dialog fills the screen with
equal margins on all four sides and a darker backdrop. Margins scale from 32px
to 80px with the viewport width (64px at 1280px). Only the page and a
floating toolbar are visible: previous/next highlight, jump to highlighted text,
open the official page in a new tab, and close. The source card and Saved evidence
retain the capture details outside this preview.

Each source card shows its title, capture label, excerpt, and the single green
action. Saved evidence is accessible from the answer's numbered citations.

The browser cannot modify a directly embedded cross-origin website. The preview
therefore renders a controlled copy of the real HTML, with source scripts, forms,
embedded documents and event handlers removed. This is a visual source preview,
not a fully interactive NPS browsing session. Official links open original pages.
Stylesheets and images load from NPS; the original Google font stylesheet is also
allowed. The frame has no script permission, and its own CSP disables scripts,
forms and connections. Only the host app inserts highlights and opens containing
sections. No provider/model request is made when opening a preview.

Live HTML is fetched only for a known document's approved NPS visitor URL, with
bounded timeouts and a 2 MiB response limit. Redirects are rejected, credentials
are not sent, and no arbitrary URL parameter exists. Fetch errors are shown with
a retry action. Missing live quotes are explicitly reported and never approximated.
The official-page link also includes the current quote as a browser text fragment.
Browser support and live-page changes may affect highlighting in that external tab.

The preview API also provides saved HTML whose SHA-256 matches the document's
recorded raw hash. This reader representation keeps source text, headings, lists and tables.
Original attributes, navigation,
forms, embedded resources and comments are removed. The frame runs with
`allow-same-origin` so the app can scroll and highlight it, without `allow-scripts`.
No live-page fetch is involved in the reader API. The dialog shows original PDFs
without inline highlighting; Saved evidence retains their recorded text and quotes.

Whitespace-only normalization lets a quote span inline markup. Missing quotes
are reported rather than approximated. Repeated exact matches are counted.
Missing or changed saved files produce an explicit preview error; a mismatched
document capture cannot silently replace the answer's source.

The Vercel packaging configuration now includes saved HTML and the small HTML
parser. PDF bytes, crawl manifests, credentials and run artifacts stay excluded.
This branch has been verified locally; deployment has not been tested.

## Local chat

The normal local preview uses real configured chat and accepts arbitrary visitor
questions. From this isolated checkout, reuse the existing project's environment
without copying credentials into the branch:

```sh
PYTHONPATH=src /Users/robin/Build/Personal/parkguide-ai/.venv/bin/python \
  scripts/run_source_preview_local.py \
  --env-file /Users/robin/Build/Personal/parkguide-ai/.env
```

Open http://127.0.0.1:8537. The runner loads credentials into this process only;
the database, chat implementation, cache and budget ledger belong to this checkout.
It does not patch metadata or replay recorded answers.

## Recorded-answer demonstration

Run from this isolated checkout using the project's installed Python environment:

```sh
PYTHONPATH=src /path/to/python scripts/run_source_preview_demo.py
```

The default URL is http://127.0.0.1:8537. This local-only runner replays archived
answers for UI inspection; it makes no model requests. Choose Yosemite and ask:

- `Can I carry my dog to Vernal Fall?`
- `Can I walk my pet dog on the paved road to Mirror Lake?`

The runner also supports the archived Grand Canyon Cedar Ridge distance question.
Other questions produce an explicit demo message. Use the normal server with
`PARKGUIDE_WEB_PORT=8537 python -m parkguide.web` for real configured chat.

Verification: 130 Python source/API/packaging/cache checks and 14 Node request/
highlight checks passed. TypeScript/Vite build and lint passed, retaining the
existing bundle-size and Fast Refresh warnings. Browser checks confirmed exact
quote highlights, automatic scrolling, two-quote navigation, and a 375px mobile
view without horizontal overflow. Screenshots are under `artifacts/source-preview/`.

The full website highlight iteration passed 114 Python API/source checks and 14
Node request/matching checks, plus build and lint. Browser verification used a
fresh Mirror Lake answer: both exact quotes were marked within the full live NPS
page alongside its original photograph and styling; Next changed the active
quote and scrolled to it. Switching to Saved evidence retained the same quote.
The screenshot `inline-highlight.jpg` records the full-page result.

The minimal dialog iteration passed build, lint, and diff checks. Browser
inspection measured 16px on every side at 1280×720, with a 70% black backdrop.
Both exact quotes remained marked; next/jump controls, the external link target,
close, and focus restoration were verified. Only the page and floating toolbar
appear in the successful state. `minimal-dialog.jpg` records this layout.

The earlier margin refinement used 32px on every side. Build and lint
passed; browser inspection confirmed all four margins and the active highlight.
`minimal-dialog-32px.jpg` records the updated size.

The current card action and larger dialog margins passed build, lint and diff
checks. Browser inspection confirmed green icon buttons at the top right,
64px dialog margins at 1280px, and 32px margins at 375px. The cards fit the narrow
viewport without horizontal overflow. A fresh Yellowstone answer opened the
Safety page and highlighted its exact bison quote. Screenshots:
`prominent-source-card.jpg` and `roomier-dialog.jpg`.
