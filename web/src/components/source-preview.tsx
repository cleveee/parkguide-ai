import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { ArrowLeftIcon, ArrowRightIcon, ExternalLinkIcon, ScanTextIcon, XIcon } from "lucide-react"

import { Source } from "@/components/ai-elements/sources"
import { Button } from "@/components/ui/button"
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { ApiError, getSourcePreview, type SourcePage, type SourcePreview } from "@/lib/api"
import { pageWitnesses, highlightedPreview } from "@/lib/source-preview"

export function SourcePreviewButton({ page, focusClaim, prominent = false }: { page: SourcePage; focusClaim?: number | null; prominent?: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size={prominent ? "default" : "sm"} variant={prominent ? "default" : "outline"}>
          <ScanTextIcon data-icon="inline-start" />
          {prominent ? "Open source" : "Preview source"}
        </Button>
      </DialogTrigger>
      <DialogContent
        showCloseButton={false}
        overlayClassName="bg-black/70 data-open:animate-none data-closed:animate-none"
        className="inset-[max(clamp(2rem,5vw,5rem),env(safe-area-inset-top),env(safe-area-inset-right),env(safe-area-inset-bottom),env(safe-area-inset-left))] flex w-auto max-w-none translate-x-0 translate-y-0 flex-col gap-0 overflow-hidden bg-white p-0 duration-0 sm:max-w-none data-open:animate-none data-closed:animate-none"
      >
        <DialogTitle className="sr-only">Source page: {page.title}</DialogTitle>
        <DialogDescription className="sr-only">
          Live official NPS page with exact cited text highlighted. The answer used the saved capture from {page.captured_label}.
        </DialogDescription>
        {open && <PreviewBody key={page.source_url} page={page} focusClaim={focusClaim} />}
      </DialogContent>
    </Dialog>
  )
}

function PreviewControl({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="bottom" sideOffset={8}>{label}</TooltipContent>
    </Tooltip>
  )
}

function PreviewBody({ page, focusClaim }: { page: SourcePage; focusClaim?: number | null }) {
  const [preview, setPreview] = useState<SourcePreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const witnesses = useMemo(() => pageWitnesses(page), [page])
  const [selected, setSelected] = useState(() => Math.max(0, witnesses.findIndex((witness) => focusClaim && witness.claims.includes(focusClaim))))
  const frame = useRef<HTMLIFrameElement>(null)
  const docId = page.passages[0]?.doc_id
  useEffect(() => {
    const controller = new AbortController()
    if (!docId) return
    getSourcePreview(docId, controller.signal, "website").then((value) => {
      if (controller.signal.aborted) return
      if (value.source_url !== page.source_url || value.crawled_at !== page.crawled_at) {
        setError("This saved page has changed since the answer was recorded. Open Saved evidence to review the original cited passage.")
        return
      }
      setPreview(value)
    }).catch((reason) => {
      if (!controller.signal.aborted) setError(reason instanceof ApiError ? reason.message : "Could not load the source page.")
    })
    return () => controller.abort()
  }, [docId, page.source_url, page.crawled_at, attempt])
  const highlighted = useMemo(() => preview ? highlightedPreview(preview.html, witnesses, preview.mode === "html_page" ? "website" : "reader") : null, [preview, witnesses])
  const jumpToQuote = () => {
    const document = frame.current?.contentDocument
    if (!document) return
    document.querySelectorAll("mark[data-active]").forEach((mark) => mark.removeAttribute("data-active"))
    const marks = document.querySelectorAll('mark[data-witness~="' + selected + '"]')
    marks.forEach((mark) => {
      mark.setAttribute("data-active", "true")
      for (let parent = mark.parentElement; parent; parent = parent.parentElement) {
        parent.removeAttribute("hidden")
        if (parent.getAttribute("aria-hidden") === "true") parent.removeAttribute("aria-hidden")
        if (parent.classList.contains("collapse")) parent.classList.add("show")
        if (parent.id) document.querySelectorAll("button[aria-controls]").forEach((button) => {
          if (button.getAttribute("aria-controls")?.split(/\s/u).includes(parent.id)) button.setAttribute("aria-expanded", "true")
        })
      }
    })
    marks[0]?.scrollIntoView({ block: "center", behavior: "instant" })
  }
  useEffect(jumpToQuote, [selected, highlighted])
  const witness = witnesses[selected]
  const count = highlighted?.counts[selected] ?? 0
  const official = page.page_type === "pdf"
    ? page.passages.find((passage) => witness && passage.claim_numbers.some((claim) => witness.claims.includes(claim)))?.passage_url ?? page.source_url
    : page.source_url + (witness ? "#:~:text=" + encodeURIComponent(witness.quote.trim().replace(/\s+/gu, " ")).replace(/-/gu, "%2D") : "")
  const canJump = page.page_type !== "pdf" && count > 0
  const jumpLabel = highlighted && !count ? "Cited text is not highlighted on this page" : "Jump to highlighted text"
  return (
    <>
      <TooltipProvider>
        <div role="toolbar" aria-label="Source page controls" className="absolute top-4 right-4 z-10 flex items-center gap-1 rounded-full border bg-background p-1 text-foreground shadow-lg">
          {witnesses.length > 1 && (
            <>
              <PreviewControl label="Previous highlight">
                <Button size="icon-sm" variant="ghost" aria-label="Previous highlight" disabled={selected === 0} onClick={() => setSelected(selected - 1)}><ArrowLeftIcon /></Button>
              </PreviewControl>
              <PreviewControl label="Next highlight">
                <Button size="icon-sm" variant="ghost" aria-label="Next highlight" disabled={selected === witnesses.length - 1} onClick={() => setSelected(selected + 1)}><ArrowRightIcon /></Button>
              </PreviewControl>
            </>
          )}
          {witness && (
            <PreviewControl label={jumpLabel}>
              <Button size="icon-sm" variant="ghost" aria-label={jumpLabel} disabled={!canJump} onClick={jumpToQuote}><ScanTextIcon /></Button>
            </PreviewControl>
          )}
          <PreviewControl label="Open official page in a new tab">
            <Button size="icon-sm" variant="ghost" asChild>
              <Source href={official} aria-label="Open official page in a new tab"><ExternalLinkIcon /></Source>
            </Button>
          </PreviewControl>
          <PreviewControl label="Close preview">
            <DialogClose asChild>
              <Button size="icon-sm" variant="ghost" aria-label="Close preview"><XIcon /></Button>
            </DialogClose>
          </PreviewControl>
        </div>
      </TooltipProvider>
      {error || !docId ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
          <p role="alert" className="max-w-md text-center text-sm text-pretty">{error ?? "No saved document was recorded for this source."}</p>
          {docId && <Button variant="outline" size="sm" onClick={() => { setError(null); setAttempt(attempt + 1) }}>Retry preview</Button>}
        </div>
      ) : highlighted ? (
        page.page_type === "pdf"
          ? <iframe title={"Official NPS PDF: " + page.title} src={official} className="min-h-0 w-full flex-1 border-0 bg-white" />
          : <iframe ref={frame} title={"Highlighted NPS website: " + page.title} srcDoc={highlighted.html} sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" referrerPolicy="no-referrer" onLoad={jumpToQuote} className="min-h-0 w-full flex-1 border-0 bg-white" />
      ) : (
        <div className="flex-1 space-y-4 p-8" role="status" aria-label="Loading source page"><Skeleton className="h-8 w-2/3" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-5/6" /><Skeleton className="h-4 w-full" /><span className="sr-only">Loading source page…</span></div>
      )}
      {highlighted && witness && page.page_type !== "pdf" && !count && (
        <p role="status" className="absolute bottom-4 left-1/2 max-w-[calc(100%-2rem)] -translate-x-1/2 rounded-lg border bg-background px-3 py-2 text-center text-xs text-pretty text-muted-foreground shadow-sm">
          Cited text wasn’t found on this live page. Check Saved evidence for the original passage.
        </p>
      )}
    </>
  )
}
