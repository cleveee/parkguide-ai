import { ChevronDownIcon, ExternalLinkIcon, FileTextIcon } from "lucide-react"

import { Source } from "@/components/ai-elements/sources"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { parkName, type SourcePage, type SourcePassage } from "@/lib/api"
import { formatDate, pageTypeLabel } from "@/lib/format"

export function Excerpt({ passage }: { passage: SourcePassage }) {
  if (!passage.excerpt) return null
  return (
    <blockquote className="border-l-2 border-border pl-3 text-pretty [overflow-wrap:anywhere]">
      {passage.excerpt_leading_omission && "…"}
      {passage.excerpt}
      {passage.excerpt_truncated && "…"}
    </blockquote>
  )
}

export function passageLocation(passage: SourcePassage) {
  const parts = [passage.heading_path || null, passage.pdf_start_page ? `PDF page ${passage.pdf_start_page}` : null]
  return parts.filter(Boolean).join(" · ")
}

export function SourceMeta({ page }: { page: SourcePage }) {
  return (
    <p className="text-xs text-pretty text-muted-foreground">
      {parkName(page.park)} · {pageTypeLabel(page.page_type)} · Source date {page.effective_date ?? "not stated"} · Saved {page.captured_label}
    </p>
  )
}

export function SourceCard({ page, onOpen }: { page: SourcePage; onOpen: () => void }) {
  const preview = page.passages.find((passage) => passage.excerpt)
  // The park and publisher are already identified elsewhere in the card.
  // Preserve the original title in the evidence dialog and title attribute.
  const suffix = ` - ${parkName(page.park)} National Park (U.S. National Park Service)`
  const title = page.title.endsWith(suffix) ? page.title.slice(0, -suffix.length) || page.title : page.title

  return (
    <article className="w-full min-w-0 rounded-xl border bg-card text-sm text-card-foreground">
      <Collapsible>
        <div className="space-y-4 p-4">
          <div className="flex items-start gap-3">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-xs font-medium tabular-nums text-primary">
              {page.number}
            </span>
            <div className="min-w-0 space-y-1">
              <h4 className="font-medium text-balance [overflow-wrap:anywhere]" title={page.title}>{title}</h4>
              <p className="flex flex-wrap gap-x-1 text-xs leading-relaxed text-muted-foreground">
                <span>{parkName(page.park)}</span>
                <span aria-hidden>·</span>
                <span title={page.captured_label}>{page.crawled_at ? `Saved ${formatDate(page.crawled_at)}` : "Save date unavailable"}</span>
                {page.page_type === "pdf" && <span>· PDF</span>}
              </p>
            </div>
          </div>

          {preview && (
            <div className="space-y-1.5 rounded-lg bg-muted/40 px-3 py-2.5">
              <p className="text-xs font-medium text-muted-foreground">Excerpt from the saved page</p>
              <blockquote className="text-sm leading-relaxed text-pretty [overflow-wrap:anywhere]">
                {preview.excerpt_leading_omission && "…"}
                {preview.excerpt}
                {preview.excerpt_truncated && "…"}
              </blockquote>
              {page.passages.length > 1 && (
                <p className="text-xs tabular-nums text-muted-foreground">
                  Preview of 1 of {page.passages.length} cited passages
                </p>
              )}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <Button size="sm" variant="outline" onClick={onOpen}>
              <FileTextIcon data-icon="inline-start" />
              Saved evidence
            </Button>
            <Source
              className="inline-flex min-h-7 items-center gap-1 rounded text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-visible:outline-2 focus-visible:outline-ring"
              href={page.source_url}
            >
              Official NPS page
              <ExternalLinkIcon className="size-3" aria-hidden />
              <span className="sr-only">(opens the current page in a new tab)</span>
            </Source>
            <CollapsibleTrigger asChild>
              <Button size="sm" variant="ghost" className="group ml-auto gap-1 text-xs text-muted-foreground" aria-label={`Details for source ${page.number}`}>
                Details
                <ChevronDownIcon className="size-3.5 group-data-[state=open]:rotate-180" aria-hidden />
              </Button>
            </CollapsibleTrigger>
          </div>
        </div>

        <CollapsibleContent>
          <div className="space-y-4 border-t p-4 text-xs">
            <dl className="grid gap-3 text-pretty sm:grid-cols-2">
              <div className="space-y-1">
                <dt className="text-muted-foreground">Snapshot saved</dt>
                <dd className="tabular-nums">{page.captured_label}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-muted-foreground">Source date · {pageTypeLabel(page.page_type)}</dt>
                <dd className="tabular-nums">{page.effective_date ?? "Not stated"}</dd>
              </div>
            </dl>
            <div className="space-y-1">
              <h5 className="font-medium text-balance">AI review quotes</h5>
              <p className="leading-relaxed text-pretty text-muted-foreground">
                Selected by the AI review and matched verbatim to the saved text.
                {preview && " The excerpt preview is provided for context."}
              </p>
            </div>
            <ul className="space-y-4">
              {page.passages.map((passage) => (
                <li key={passage.chunk_id} className="space-y-2 [overflow-wrap:anywhere]">
                  <p className="leading-relaxed text-pretty text-muted-foreground">
                    <span className="font-medium tabular-nums">Claim{passage.claim_numbers.length === 1 ? "" : "s"} {passage.claim_numbers.join(", ")}</span>
                    {passageLocation(passage) && <span> · {passageLocation(passage)}</span>}
                  </p>
                  {passage.reviewer_witnesses.length > 0 ? (
                    <ul className="space-y-2 border-l-2 border-primary/30 pl-3">
                      {passage.reviewer_witnesses.map((witness, index) => (
                        <li key={index}>
                          <blockquote className="leading-relaxed text-pretty">
                            “{witness.quote}”
                            {passage.claim_numbers.length > 1 && (
                              <span className="ml-1 tabular-nums text-muted-foreground">· claim {witness.claim_number}</span>
                            )}
                          </blockquote>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted-foreground">No review quote recorded for this passage.</p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </article>
  )
}
