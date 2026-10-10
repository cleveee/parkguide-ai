import { ChevronDownIcon, ExternalLinkIcon, SparklesIcon } from "lucide-react"

import { Source } from "@/components/ai-elements/sources"
import { Excerpt, SourceMeta, passageLocation } from "@/components/source-card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { ChatTurn, SourcePage, SourcePassage } from "@/lib/api"
import { formatDateTime } from "@/lib/format"

/** One tab per cited passage; opens on the passage cited by `focusClaim`. */
export function PassageEvidence({ page, response, focusClaim }: { page: SourcePage; response: ChatTurn; focusClaim?: number | null }) {
  const initial = page.passages.find((passage) => focusClaim && passage.claim_numbers.includes(focusClaim)) ?? page.passages[0]
  if (page.passages.length <= 1) {
    return <div className="space-y-5">{page.passages.map((passage) => <PassagePanel key={passage.chunk_id} passage={passage} response={response} />)}</div>
  }
  return (
    <Tabs key={initial?.chunk_id} defaultValue={initial?.chunk_id} className="gap-3">
      <TabsList className="h-auto flex-wrap">
        {page.passages.map((passage, index) => (
          <TabsTrigger key={passage.chunk_id} value={passage.chunk_id}>
            Passage {index + 1}
            <span className="text-muted-foreground tabular-nums">· claim {passage.claim_numbers.join(", ")}</span>
          </TabsTrigger>
        ))}
      </TabsList>
      {page.passages.map((passage) => (
        <TabsContent key={passage.chunk_id} value={passage.chunk_id}>
          <PassagePanel passage={passage} response={response} />
        </TabsContent>
      ))}
    </Tabs>
  )
}

function PassagePanel({ passage, response }: { passage: SourcePassage; response: ChatTurn }) {
  return (
    <div className="space-y-5">
      {[passage].map((passage) => (
        <section key={passage.chunk_id} className="space-y-3 rounded-lg border bg-card p-3">
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-muted-foreground">Delivered claims citing this passage</h4>
            <ol className="space-y-2">
              {passage.claim_numbers.map((number) => {
                const claim = response.claims.find((item) => item.number === number)
                const witnesses = passage.reviewer_witnesses.filter((witness) => witness.claim_number === number)
                return (
                  <li key={number} className="space-y-2 text-sm">
                    <p className="text-pretty">
                      <span className="mr-1.5 font-medium tabular-nums text-muted-foreground">{number}.</span>
                      {claim?.text}
                    </p>
                    <div className="space-y-1.5 rounded-md bg-muted/60 p-2.5 text-xs">
                      <p className="flex items-center gap-1.5 font-medium text-muted-foreground">
                        <SparklesIcon className="size-3.5" aria-hidden />
                        AI source review · a model judgment, not human verification
                      </p>
                      {claim?.review?.reason ? (
                        <p className="text-pretty text-foreground/80">Reviewer note: {claim.review.reason}</p>
                      ) : (
                        <p className="text-muted-foreground">Reviewer note not captured.</p>
                      )}
                      {witnesses.length > 0 ? (
                        <div className="space-y-1">
                          <p className="text-muted-foreground">Reviewer-selected witnesses (checked verbatim against this passage):</p>
                          <ul className="space-y-1">
                            {witnesses.map((witness, index) => (
                              <li
                                key={index}
                                className="rounded border bg-background px-2 py-1 font-mono text-[0.75rem] text-pretty [overflow-wrap:anywhere]"
                              >
                                “{witness.quote}”
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : (
                        <p className="text-muted-foreground">No reviewer witness recorded for this passage.</p>
                      )}
                    </div>
                  </li>
                )
              })}
            </ol>
          </div>

          <div className="space-y-1">
            <h4 className="text-xs font-medium text-muted-foreground">Context excerpt</h4>
            <p className="text-xs text-pretty text-muted-foreground">
              Exact words from the saved passage, picked mechanically by word overlap with the claim. This is not the reviewer's evidence; the witnesses
              above are.
            </p>
            <div className="text-sm [overflow-wrap:anywhere]">
              <Excerpt passage={passage} />
            </div>
            <p className="text-xs text-muted-foreground">
              {passageLocation(passage) || "No heading recorded"}
              {passage.source_spans.length > 0 && (
                <span className="tabular-nums">
                  {" "}
                  · Saved text offsets {passage.source_spans.map((span) => `${span.start}–${span.end}`).join(", ")}
                </span>
              )}
            </p>
          </div>

          <Collapsible>
            <CollapsibleTrigger className="group flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground">
              Full saved passage
              <ChevronDownIcon className="size-3.5 transition-transform group-data-[state=open]:rotate-180" aria-hidden />
            </CollapsibleTrigger>
            <CollapsibleContent>
              <p className="mt-2 rounded-md border bg-background p-2.5 text-xs whitespace-pre-wrap text-pretty text-foreground/85 [overflow-wrap:anywhere]">{passage.saved_text}</p>
            </CollapsibleContent>
          </Collapsible>

          {passage.pdf_start_page && (
            <Source className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground" href={passage.passage_url}>
              Official PDF at recorded starting page {passage.pdf_start_page}
              <ExternalLinkIcon className="size-3" aria-hidden />
            </Source>
          )}
        </section>
      ))}
    </div>
  )
}

export function EvidenceDialog({
  response,
  sourceNumber,
  claimNumber,
  onOpenChange,
}: {
  response: ChatTurn | null
  sourceNumber: number | null
  claimNumber: number | null
  onOpenChange: (open: boolean) => void
}) {
  const page = response?.sources.find((item) => item.number === sourceNumber) ?? null
  return (
    <Dialog open={Boolean(page)} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(85dvh,48rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
        {page && response && (
          <>
            <DialogHeader className="border-b p-4 pr-12">
              <DialogTitle className="leading-snug text-balance">
                <span className="mr-2 tabular-nums text-muted-foreground">{page.number}</span>
                {page.title}
              </DialogTitle>
              <DialogDescription asChild>
                <div className="space-y-2">
                  <SourceMeta page={page} />
                  <p className="text-xs text-pretty">
                    This is the locally saved snapshot used for the answer (captured {formatDateTime(page.crawled_at)}), not live conditions. The
                    official page may have changed since capture.
                  </p>
                  <Source className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline" href={page.source_url}>
                    Open the current official NPS page
                    <ExternalLinkIcon className="size-3" aria-hidden />
                  </Source>
                </div>
              </DialogDescription>
            </DialogHeader>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
              <div className="p-4 break-words">
                <PassageEvidence page={page} response={response} focusClaim={claimNumber} />
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
