import { SourcePreviewButton } from "@/components/source-preview"
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

export function SourceCard({ page }: { page: SourcePage }) {
  const preview = page.passages.find((passage) => passage.excerpt)
  // The park and publisher are already identified elsewhere in the card.
  // Preserve the original title in the evidence dialog and title attribute.
  const suffix = ` - ${parkName(page.park)} National Park (U.S. National Park Service)`
  const title = page.title.endsWith(suffix) ? page.title.slice(0, -suffix.length) || page.title : page.title

  return (
    <article className="w-full min-w-0 rounded-xl border bg-card text-sm text-card-foreground">
      <div className="space-y-4 p-4">
        <div className="flex items-start gap-3">
          <div className="flex min-w-0 flex-1 items-start gap-3">
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
          <SourcePreviewButton page={page} prominent />
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

      </div>
    </article>
  )
}
