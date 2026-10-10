# Frontend references and component provenance

The web app in `web/` reuses published open-source components. This file records where each one came from, its license and version, how it was installed, and every ParkGuide adaptation. The imports in `web/src` match this list.

## Visual and interaction references

| Reference | Used for | Code copied? |
|---|---|---|
| [Vercel AI Elements chatbot example](https://elements.ai-sdk.dev/examples/chatbot) (primary) | Conversation column with sticky scroll, bottom composer, collapsible sources under an answer | Components below, via the official registry |
| [AI Elements Sources](https://elements.ai-sdk.dev/components/sources) | Collapsible "sources used" group | Yes, via registry (below) |
| [assistant-ui Sources](https://www.assistant-ui.com/elements/sources) | Progressive disclosure of source groups; compact evidence cards | No. Pattern only; no assistant-ui code, package or runtime |

No assistant runtime is used: there is no AI SDK (`ai`), no `useChat`, no streaming transport and no assistant-ui runtime. The browser calls only same-origin `/api/*` on the loopback FastAPI bridge (`src/parkguide/web.py`). No external fonts, remote images, analytics or brand assets are bundled. The favicon is a simple tree glyph drawn for this project.

## Vercel AI Elements (Apache-2.0)

- Source: <https://github.com/vercel/ai-elements>, © Vercel, Inc., Apache License 2.0. The license text is in `web/src/components/ai-elements/LICENSE`, reproduced from the `ai-elements@1.9.0` npm package. Each file carries a header naming its source URL, the license and the changes.
- Installation (2026-10-10): the official CLI `ai-elements@1.9.0` runs `shadcn add https://elements.ai-sdk.dev/api/registry/<name>.json`. That command was run directly with `shadcn@4.21.4`:
  `npx shadcn@4.21.4 add -c web --overwrite https://elements.ai-sdk.dev/api/registry/{conversation,message,sources,prompt-input}.json`
  The `--overwrite` was needed only for the registry-dependency prompts. The overwritten `tooltip`, `collapsible` and `dialog` primitives were then reinstalled from the project's radix-nova shadcn style, so all primitives share one style.

| File | Upstream registry item | Exports used by ParkGuide | Adaptations |
|---|---|---|---|
| `conversation.tsx` | `conversation` | `Conversation`, `ConversationContent`, `ConversationScrollButton` | The type-only `UIMessage` import from `ai` is replaced by a structurally equivalent local type. Unused upstream exports (`ConversationEmptyState`, `ConversationDownload`, `messagesToMarkdown`) are retained unchanged. |
| `message.tsx` | `message` | `Message`, `MessageContent`, `MessageActions`, `MessageAction` | `MessageResponse` (Streamdown markdown renderer with cjk/code/math/mermaid plugins) is removed: ParkGuide renders reviewed claims as plain text and never renders model markdown or HTML. The type-only `UIMessage["role"]` is replaced by a local role union. Branch/toolbar exports are retained unchanged. |
| `sources.tsx` | `sources` | `Sources`, `SourcesTrigger` (custom children), `SourcesContent`, `Source` | None. `Source` (an `<a target="_blank" rel="noreferrer">`) is used only for links to validated official `https://www.nps.gov/{park}/planyourvisit/...` URLs supplied by the server. |
| `prompt-input.tsx` | `prompt-input` | `PromptInputProvider`, `usePromptInputController`, `PromptInput`, `PromptInputBody`, `PromptInputTextarea`, `PromptInputFooter`, `PromptInputTools`, `PromptInputSubmit` | The type-only `ChatStatus`, `FileUIPart` and `SourceDocumentUIPart` imports from `ai` are replaced by structurally equivalent local types; behavior is unchanged. Attachments are disabled at the call site with `maxFiles={0}`: a pasted or dropped file triggers the upstream `onError`, and the UI explains that attachments are unsupported. Text paste is never blocked. |

Upstream dependencies removed after installation: `ai`, `streamdown`, `@streamdown/cjk`, `@streamdown/code`, `@streamdown/math` and `@streamdown/mermaid`. After the edits above, no ParkGuide code imports them. Retained registry dependencies: `use-stick-to-bottom@1.1.6` (MIT), `nanoid@6.0.2` (MIT), `cmdk@1.1.1` (MIT, through the `command` primitive) and `lucide-react@1.55.0` (ISC).

## shadcn/ui primitives (MIT) on Radix (MIT)

- Source: <https://ui.shadcn.com>, MIT. Installed with `npx shadcn@4.21.4 init -t vite -b radix -p nova` and `npx shadcn@4.21.4 add ...` into `web/src/components/ui/`. They are built on the unified `radix-ui@1.7.0` package (MIT). `components.json` records the `radix-nova` style.
- Used by ParkGuide surfaces: `alert-dialog` (confirm clearing a conversation), `alert` (request errors next to the turn), `badge`, `button`, `collapsible`, `dialog` (evidence preview, How it works), `input`, `scroll-area`, `select` (park selector, corpus filters), `sheet` (mobile menu, inspector below 1280 px, document detail), `skeleton`, `spinner`, `table`, `tabs` (inspector views, corpus park scope) and `tooltip`.
- Installed as AI Elements registry dependencies: `button-group`, `input-group`, `dropdown-menu`, `hover-card` and `command`. `separator` and `textarea` are installed but used only indirectly.
- Adaptations: the radix-nova preset generated imports of `cn` from the npm package `cn`. Every primitive now imports `cn` from `web/src/lib/utils.ts`, the classic `clsx` + `tailwind-merge` helper, and the `cn` package is uninstalled. The preset's `@fontsource-variable/geist` webfont was removed in favor of the system font stack. Theme tokens in `web/src/index.css` use Tailwind stone neutrals and a single emerald accent (Tailwind palette oklch values). The `sheet`, `dialog` and `alert-dialog` overlays no longer use the preset's animated `backdrop-blur-xs`; they keep a plain `bg-black/20` dim with the upstream ≤200 ms opacity/transform animations. Callers widen sheets with `data-[side=right]:sm:max-w-xl`, because a plain `sm:max-w-*` class cannot override the primitive's `data-[side=right]:sm:max-w-sm` variant. No primitive's keyboard or focus behavior was changed.

One primitive system (Radix via shadcn/ui) is used on every surface. No Base UI or React Aria primitives are mixed in.

## Other packages

| Package | Version | License | Purpose |
|---|---|---|---|
| react / react-dom | 19.3.0 | MIT | UI |
| vite, @vitejs/plugin-react | 8.3.4, 6.1.2 | MIT | Build and development server |
| typescript | 6.0.3 | Apache-2.0 | Typecheck (`tsc -b`) |
| tailwindcss, @tailwindcss/vite | 4.3.3 | MIT | Styling (defaults only) |
| tw-animate-css | 1.4.0 | MIT | shadcn enter/exit utilities |
| clsx, tailwind-merge | 2.1.1, 3.7.0 | MIT | `cn` helper |
| class-variance-authority | 0.7.1 | Apache-2.0 | shadcn variants |
| motion | 14.1.0 | MIT | `motion/react`: one ≤150 ms opacity/translate entrance on delivered answers, disabled under reduced motion |
| shadcn | 4.21.4 | MIT | CLI and `shadcn/tailwind.css` base layer |
| oxlint | 1.87.0 | MIT | Lint (development only) |

Exact resolved versions and integrity hashes are pinned in `web/package-lock.json`.

## Python bridge

`fastapi==0.141.1` (MIT) is the only added Python package. It is the newest release that installs without new transitive packages: 0.142.0 and later add `opentelemetry-api`. It uses the already locked `starlette==1.7.0`, `pydantic==2.14.0`, `annotated-doc==0.0.5` and `uvicorn==0.54.0`. Both lock files pin it; no other package was upgraded (`pip freeze` matches `requirements-full.lock` and `pip check` is clean).
