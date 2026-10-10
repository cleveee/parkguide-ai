import { ExternalLinkIcon, FileTextIcon } from "lucide-react"

import { Source } from "@/components/ai-elements/sources"
import { Button } from "@/components/ui/button"
import { parkName, type SourcePage, type SourcePassage } from "@/lib/api"
import { pageTypeLabel } from "@/lib/format"

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
  return (
    <article className="w-full rounded-lg border bg-card p-3 text-sm text-card-foreground">
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-medium tabular-nums text-muted-foreground">
          {page.number}
        </span>
        <div className="min-w-0 space-y-0.5">
          <h4 className="font-medium text-balance text-foreground">{page.title}</h4>
          <SourceMeta page={page} />
        </div>
      </div>
      <ul className="mt-3 space-y-3">
        {page.passages.map((passage) => (
          <li key={passage.chunk_id} className="space-y-1.5 text-xs [overflow-wrap:anywhere]">
            <p className="text-muted-foreground">
              Cited for claim {passage.claim_numbers.join(", ")}
              {passageLocation(passage) && <span> · {passageLocation(passage)}</span>}
            </p>
            {passage.reviewer_witnesses.length > 0 ? (
              <div className="space-y-1">
                <p className="font-medium text-muted-foreground">Reviewer witness (checked verbatim against the saved passage)</p>
                {passage.reviewer_witnesses.map((witness, index) => (
                  <blockquote key={index} className="border-l-2 border-primary/60 pl-3 text-pretty text-foreground">
                    “{witness.quote}”<span className="ml-1 text-muted-foreground tabular-nums">· claim {witness.claim_number}</span>
                  </blockquote>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground">No reviewer witness recorded for this passage.</p>
            )}
            {passage.excerpt && (
              <div className="space-y-0.5">
                <p className="font-medium text-muted-foreground">Context excerpt (chosen by word overlap, not by the reviewer)</p>
                <div className="text-muted-foreground">
                  <Excerpt passage={passage} />
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="xs" variant="outline" onClick={onOpen}>
          <FileTextIcon data-icon="inline-start" />
          Saved evidence
        </Button>
        <Source
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
          href={page.source_url}
        >
          Official NPS page
          <ExternalLinkIcon className="size-3" aria-hidden />
          <span className="sr-only">(opens the current page in a new tab)</span>
        </Source>
      </div>
    </article>
  )
}
