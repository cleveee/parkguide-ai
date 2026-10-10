import { createContext, useContext, useState } from "react"
import { CheckIcon, CopyIcon, DownloadIcon } from "lucide-react"

import { PassageEvidence } from "@/components/evidence-dialog"
import { SourceMeta } from "@/components/source-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { parkName, type ChatTurn, type Derivation, type EmbeddingObservation, type LedgerKind, type LedgerWindow } from "@/lib/api"
import { NOT_CAPTURED, formatCount, formatMs, formatScore, formatUsd } from "@/lib/format"
import { cn } from "@/lib/utils"

function Row({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  const missing = value === NOT_CAPTURED
  return (
    <div className="flex items-baseline justify-between gap-4 py-1 text-xs">
      <dt className="text-muted-foreground" title={hint}>
        {label}
      </dt>
      <dd className={cn("min-w-0 text-right tabular-nums break-words", missing && "text-muted-foreground italic")}>{value}</dd>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-xs font-medium text-foreground">{title}</h3>
      {children}
    </section>
  )
}

function exportJson(turn: ChatTurn) {
  // The turn object already contains only reviewed output, validated stored
  // evidence and safe diagnostics produced by the local server.
  return JSON.stringify({ exported_at: new Date().toISOString(), history_storage: "browser_local_storage", turn }, null, 2)
}

function ExportButtons({ turn }: { turn: ChatTurn }) {
  const [copied, setCopied] = useState<"ok" | "failed" | null>(null)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(exportJson(turn))
      setCopied("ok")
    } catch {
      setCopied("failed")
    }
    window.setTimeout(() => setCopied(null), 1600)
  }
  const download = () => {
    const blob = new Blob([exportJson(turn)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `parkguide-turn-${turn.turn_id.slice(0, 8)}.json`
    document.body.append(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="flex items-center gap-1">
      <Button variant="outline" size="xs" onClick={copy}>
        {copied === "ok" ? <CheckIcon data-icon="inline-start" /> : <CopyIcon data-icon="inline-start" />}
        {copied === "ok" ? "Copied" : copied === "failed" ? "Copy failed" : "Copy JSON"}
      </Button>
      <Button variant="outline" size="xs" onClick={download}>
        <DownloadIcon data-icon="inline-start" />
        Download
      </Button>
    </div>
  )
}

function EvidenceTab({ turn }: { turn: ChatTurn }) {
  if (turn.status !== "answer") {
    return (
      <div className="space-y-3 text-sm">
        <p className="text-pretty">{turn.text}</p>
        {turn.reason && (
          <dl className="rounded-lg border bg-card p-3">
            <Row label="Stage" value={turn.reason.category.replaceAll("_", " ")} />
            <Row label="Reason code" value={<code className="font-mono">{turn.reason.code}</code>} />
            <p className="pt-1 text-xs text-pretty text-muted-foreground">{turn.reason.detail}</p>
          </dl>
        )}
        <p className="text-xs text-pretty text-muted-foreground">No source cards are shown because no reviewed answer was delivered.</p>
      </div>
    )
  }
  return (
    <div className="space-y-5">
      <Section title="Delivered claims">
        <ol className="space-y-1.5 text-sm">
          {turn.claims.map((claim) => (
            <li key={claim.number} className="text-pretty">
              <span className="mr-1.5 tabular-nums text-muted-foreground">{claim.number}.</span>
              {claim.text}
              <span className="ml-1 text-xs tabular-nums text-muted-foreground">[{claim.source_numbers.join(", ")}]</span>
            </li>
          ))}
        </ol>
        {(turn.inspector.review.withheld_claims ?? 0) > 0 && (
          <p className="text-xs text-pretty text-muted-foreground">
            {turn.inspector.review.withheld_claims} drafted claim(s) failed source review and were withheld. Their text is not shown or exported.
          </p>
        )}
      </Section>
      {turn.inspector.derivation && <DerivationSection derivation={turn.inspector.derivation} />}
      {turn.sources.map((page) => (
        <Section key={page.number} title={`${page.number}. ${page.title}`}>
          <SourceMeta page={page} />
          <PassageEvidence page={page} response={turn} />
        </Section>
      ))}
    </div>
  )
}

function DerivationSection({ derivation }: { derivation: Derivation }) {
  return (
    <Section title="Table calculation">
      <div className="space-y-2 rounded-lg border bg-card p-3 text-xs">
        <dl>
          <Row label="Column" value={derivation.column ?? NOT_CAPTURED} />
          <Row label="Operation" value={derivation.operation?.replaceAll("_", " ") ?? NOT_CAPTURED} />
          <Row label="Equation" value={<code className="font-mono">{derivation.equation ?? NOT_CAPTURED}</code>} />
          <Row label="Unit" value={derivation.unit ?? NOT_CAPTURED} />
        </dl>
        <Table className="text-xs">
          <TableHeader>
            <TableRow>
              <TableHead>Row</TableHead>
              <TableHead>Saved cell</TableHead>
              <TableHead className="text-right">Value used</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {derivation.operands.map((operand, index) => (
              <TableRow key={index}>
                <TableCell>{operand.row_label}</TableCell>
                <TableCell className="font-mono">{operand.source_cell}</TableCell>
                <TableCell className="text-right tabular-nums">{operand.value}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="text-pretty text-muted-foreground">{derivation.note}</p>
      </div>
    </Section>
  )
}

function RetrievalTab({ turn }: { turn: ChatTurn }) {
  const retrieval = turn.inspector.retrieval
  if (!retrieval.ran) {
    return (
      <p className="text-sm text-pretty text-muted-foreground">
        Retrieval did not run for this turn{turn.reason ? ` (${turn.reason.code})` : ""}, so there is no query, search result or score to show.
      </p>
    )
  }
  const labels = retrieval.score_labels
  return (
    <div className="space-y-5">
      <Section title="Query">
        <p className="rounded-md bg-muted/60 p-2 font-mono text-xs break-words">{retrieval.query}</p>
        {retrieval.keyword_query && retrieval.keyword_query !== retrieval.query && (
          <div className="space-y-1 text-xs">
            <p className="text-muted-foreground">Keyword search keeps earlier subjects and removes repeated terms. For concrete follow-ups, matches must include a current subject. Semantic search uses the full context above.</p>
            <p className="rounded-md bg-muted/60 p-2 font-mono break-words">{retrieval.keyword_query}</p>
          </div>
        )}
        <dl>
          {Boolean(retrieval.keyword_current_terms?.length) && <Row label="Keyword match requires any of" value={retrieval.keyword_current_terms!.join(", ")} />}
          <Row label="Park filter" value={retrieval.filters.parks.map(parkName).join(", ") || "None"} />
          {retrieval.filters.source_url_count > 0 && <Row label="Table-page URL filter" value={`${retrieval.filters.source_url_count} pages`} />}
          <Row label="Mode" value={retrieval.mode ?? NOT_CAPTURED} />
          <Row label="Index build" value={`${retrieval.build_strategy} · ${retrieval.build_id?.slice(0, 12) ?? "?"}`} />
          <Row label="Reranking" value={retrieval.rerank_enabled ? "On (local cross-encoder)" : "Off"} />
          {turn.runtime && (
            <Row
              label="Runtime profile"
              value={turn.runtime.profile === "vercel" ? "Hosted (Vercel), reranker not installed" : "Local"}
              hint={turn.runtime.profile === "vercel" ? turn.runtime.evaluation_note : undefined}
            />
          )}
        </dl>
      </Section>
      <Section title="Counts">
        <dl>
          <Row label="Eligible passages in park" value={formatCount(retrieval.eligible_count)} />
          <Row label="Candidates (requested)" value={`${formatCount(retrieval.candidate_count)} (${formatCount(retrieval.requested_candidates)})`} />
          <Row label="Final ranked" value={formatCount(retrieval.final_count)} />
          <Row label="Sent to the model as context" value={formatCount(retrieval.context_count)} />
          {retrieval.shortfall && <Row label="Shortfall" value="Fewer candidates than requested" />}
        </dl>
      </Section>
      <Section title="Local retrieval timing">
        <dl>
          <Row label="Total retrieval (contains the rows below)" value={formatMs(retrieval.timings_ms.total_ms)} />
          <Row label="⤷ Load index rows" value={formatMs(retrieval.timings_ms.load_ms)} />
          <Row label="⤷ BM25 + cosine + fusion" value={formatMs(retrieval.timings_ms.retrieval_ms)} />
          <Row label="⤷ Rerank" value={retrieval.rerank_enabled ? formatMs(retrieval.timings_ms.rerank_ms) : "Not run"} />
        </dl>
        <p className="text-xs text-muted-foreground">Query embedding happens before retrieval and is not included here.</p>
      </Section>
      <Section title="Ranked candidates">
        <p className="text-xs text-pretty text-muted-foreground">
          Scores are ranking signals only. They are not probabilities that a passage is true or relevant.
        </p>
        <div className="overflow-x-auto rounded-lg border">
          <Table className="text-xs">
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">#</TableHead>
                <TableHead>Passage</TableHead>
                {(["rerank", "rrf", "dense", "bm25"] as const).map((key) => (
                  <TableHead key={key} className="text-right">
                    <Tooltip>
                      <TooltipTrigger className="cursor-help underline decoration-dotted underline-offset-2">
                        {{ rerank: "Reranker", rrf: "RRF", dense: "Cosine", bm25: "BM25" }[key]}
                      </TooltipTrigger>
                      <TooltipContent>{labels[key]}</TooltipContent>
                    </Tooltip>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {retrieval.candidates.map((candidate) => (
                <TableRow key={candidate.chunk_id} className={cn(candidate.cited && "bg-primary/5")}>
                  <TableCell className="align-top tabular-nums">
                    {candidate.post_rank}
                    {candidate.pre_rank !== null && candidate.pre_rank !== candidate.post_rank && (
                      <span className="block text-[0.688rem] text-muted-foreground">was {candidate.pre_rank}</span>
                    )}
                  </TableCell>
                  <TableCell className="max-w-56 align-top whitespace-normal">
                    <p className="font-medium text-pretty">{candidate.title}</p>
                    <p className="line-clamp-1 text-muted-foreground">{candidate.heading_path}</p>
                    <p className="mt-0.5 line-clamp-2 text-muted-foreground">{candidate.snippet}</p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {!candidate.in_selected_park && <Badge variant="destructive">Outside selected park ({parkName(candidate.park)})</Badge>}
                      {candidate.cited && <Badge>Cited</Badge>}
                      {candidate.in_context && !candidate.cited && <Badge variant="outline">Context, not cited</Badge>}
                    </div>
                  </TableCell>
                  {(["rerank", "rrf", "dense", "bm25"] as const).map((key) => (
                    <TableCell key={key} className="text-right align-top font-mono tabular-nums">
                      {formatScore(candidate.scores[key])}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {retrieval.context_selection && (
          <p className="text-xs text-muted-foreground">Context selection: {retrieval.context_selection.method}</p>
        )}
      </Section>
    </div>
  )
}

type StepState = "done" | "skipped" | "stopped" | "failed"
type Where = "local" | "azure" | "browser"

const WHERE_LABEL: Record<Where, string> = { local: "This computer", azure: "Azure (remote)", browser: "Browser ↔ local server" }
// The hosted (Vercel) profile runs the "local" steps in its server function.
const HOSTED_WHERE_LABEL: Record<Where, string> = { local: "Server function", azure: "Azure (remote)", browser: "Browser ↔ server" }
const HostedContext = createContext(false)

function Step({ state, title, where, children }: { state: StepState; title: string; where: Where; children?: React.ReactNode }) {
  const labels = useContext(HostedContext) ? HOSTED_WHERE_LABEL : WHERE_LABEL
  const tone = { done: "bg-primary", skipped: "bg-border", stopped: "bg-muted-foreground", failed: "bg-destructive" }[state]
  const label = { done: "ran", skipped: "not run", stopped: "stopped here", failed: "failed" }[state]
  return (
    <li className="relative pb-4 pl-5 last:pb-0">
      <span className={cn("absolute top-1.5 left-0 size-2 rounded-full", tone)} aria-hidden />
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="text-xs font-medium">{title}</h4>
        <span className="shrink-0 text-[0.688rem] text-muted-foreground">
          {labels[where]} · {label}
        </span>
      </div>
      {children && <div className="mt-1 space-y-0.5 text-xs text-pretty text-muted-foreground">{children}</div>}
    </li>
  )
}

const EMBEDDING_TEXT: Record<EmbeddingObservation["status"], string> = {
  not_requested: "Not requested: the turn stopped before retrieval.",
  not_captured: "The embedder was called, but the budget ledger could not be read, so whether Azure was contacted is not captured.",
  azure_request_recorded: "The budget ledger recorded an embedding call to Azure during this request.",
  azure_attempt_failed_recorded: "The budget ledger recorded an embedding attempt that did not report usage.",
  no_azure_request_recorded: "No embedding call was recorded in the ledger window, consistent with reusing a locally cached vector.",
}

function LedgerSection({ window }: { window: LedgerWindow }) {
  if (!window.captured) {
    return (
      <Section title="Paid-call ledger window">
        <p className="text-xs text-muted-foreground">Not captured: {window.reason}</p>
      </Section>
    )
  }
  const kinds = Object.entries(window.by_kind) as [string, LedgerKind][]
  return (
    <Section title="Paid-call ledger window (this request)">
      <dl>
        <Row label="Recorded events" value={formatCount(window.events)} />
        <Row label="Estimated cost, all recorded events" value={formatUsd(window.cost_estimate_usd)} />
      </dl>
      {kinds.map(([kind, bucket]) => (
        <dl key={kind} className="rounded-md border p-2">
          <p className="pb-1 text-xs font-medium">
            {kind === "generation" ? "Generation (answer drafting and claim review)" : kind === "embedding" ? "Embedding" : "Other"}
          </p>
          <Row
            label="Events · reported / failed / unsettled"
            value={`${bucket.events} · ${bucket.reported_usage} / ${bucket.failed_attempts} / ${bucket.unsettled_reservations}`}
          />
          <Row label="Tokens in / out (reported only)" value={`${formatCount(bucket.input_tokens)} / ${formatCount(bucket.output_tokens)}`} />
          {bucket.events_without_token_usage > 0 && <Row label="Events without reported usage" value={formatCount(bucket.events_without_token_usage)} />}
          <Row label="Estimated cost" value={formatUsd(bucket.cost_estimate_usd)} />
        </dl>
      ))}
      <p className="text-xs text-pretty text-muted-foreground">
        {window.basis}
        {window.includes_reserved_maximums && " Calls without reported usage are counted at their reserved maximum."} {window.limitation}
      </p>
    </Section>
  )
}

function DataFlowTab({ turn }: { turn: ChatTurn }) {
  const { retrieval, embedding, generation, review } = turn.inspector
  const category = turn.reason?.category
  const preflightStopped = category === "local_preflight"
  const park = parkName(turn.selected_park)
  const remoteEmbedding = embedding.status === "azure_request_recorded" || embedding.status === "azure_attempt_failed_recorded"
  const outputRejected = category === "validation_failure" && turn.inspector.guard_errors.length === 0 && turn.inspector.integrity_errors.length === 0
  const checksFailed = turn.inspector.guard_errors.length > 0 || turn.inspector.integrity_errors.length > 0
  const hosted = turn.runtime?.profile === "vercel"
  return (
    <HostedContext.Provider value={hosted}>
    <div className="space-y-5">
      <ol>
        <Step state="done" where="browser" title={hosted ? "Question sent to the ParkGuide server function" : "Question sent to the local server (127.0.0.1)"}>
          <p>
            Question and selected park ({park}), plus {turn.history.messages_received} prior message(s) from this browser’s saved conversation.
          </p>
          <p>
            {turn.history.scope_reset
              ? "Messages mentioning another park were excluded; the remaining selected-park context was preserved."
              : `${turn.history.messages_used} prior message(s) were used as conversation context.`}
          </p>
        </Step>
        <Step state={preflightStopped ? "stopped" : "done"} where="local" title="Preflight checks">
          {preflightStopped
            ? `Stopped locally (${turn.reason?.code}). No embedding, search or model call was made.`
            : "No recognized other-park, live-information or private-record pattern matched. These checks only recognize certain wordings, so a different phrasing can continue to the steps below."}
        </Step>
        <Step
          state={embedding.status === "not_requested" ? "skipped" : embedding.status === "azure_attempt_failed_recorded" ? "failed" : "done"}
          where={remoteEmbedding ? "azure" : "local"}
          title="Query embedding"
        >
          <p>{EMBEDDING_TEXT[embedding.status]}</p>
          {embedding.status !== "not_requested" && (
            <>
              <p>
                Cache files for this query hash were {embedding.cache_file_present_before_call ? "present" : "absent"} just before the call (a file
                observation; another process could change it).
              </p>
              {embedding.query_sha256 && <p className="font-mono break-all">query sha256 {embedding.query_sha256}</p>}
              <p className="tabular-nums">Embedding step wall time {formatMs(embedding.elapsed_ms)}</p>
            </>
          )}
        </Step>
        <Step state={retrieval.ran ? "done" : "skipped"} where="local" title="Search: SQLite + NumPy cosine + BM25 + fusion">
          {retrieval.ran && (
            <p className="tabular-nums">
              {formatCount(retrieval.candidate_count)} candidates from {formatCount(retrieval.eligible_count)} saved {park} passages · scoring{" "}
              {formatMs(retrieval.timings_ms.retrieval_ms)}
            </p>
          )}
        </Step>
        <Step state={retrieval.ran && retrieval.rerank_enabled ? "done" : "skipped"} where="local" title="Reranking (cross-encoder, offline)">
          {retrieval.ran && retrieval.rerank_enabled && <p className="tabular-nums">{formatMs(retrieval.timings_ms.rerank_ms)}</p>}
          {turn.runtime?.profile === "vercel" && <p>Not installed in the hosted version; ranking is reciprocal-rank fusion only.</p>}
        </Step>
        {category === "scope_check" && (
          <Step state="stopped" where="local" title="Selected-park source check">
            <p>{turn.reason?.detail}</p>
          </Step>
        )}
        <Step state={generation.ran ? (outputRejected ? "failed" : "done") : "skipped"} where="azure" title="Answer drafting (Luna)">
          {generation.ran && (
            <>
              <p>Sent: question, {retrieval.context_count} selected snippet(s) and bounded prior conversation.</p>
              {outputRejected && <p>The reply failed local schema or citation validation ({turn.reason?.code}).</p>}
              <p>Returned model: {generation.returned_model ?? NOT_CAPTURED}</p>
              <p className="tabular-nums">
                Final successful call: {formatCount(generation.input_tokens)} in / {formatCount(generation.output_tokens)} out tokens ·{" "}
                {formatMs(generation.elapsed_ms)} · est. {formatUsd(generation.cost_estimate_usd)}
              </p>
            </>
          )}
        </Step>
        <Step
          state={review.status === "not_run" ? "skipped" : review.status === "error" ? "failed" : "done"}
          where="azure"
          title="Claim source review (Luna, cited passages only)"
        >
          {review.status !== "not_run" && (
            <>
              <p>
                {review.status === "passed" && "All drafted claims passed source review."}
                {review.status === "partially_withheld" && `${review.withheld_claims} unsupported claim(s) withheld; their text is not shown.`}
                {review.status === "all_withheld" && "Every drafted claim was withheld."}
                {review.status === "error" &&
                  `The review did not complete validly (${review.validation_reason ?? review.error_message ?? "error"}). Nothing was delivered.`}
              </p>
              {review.status !== "error" && (
                <>
                  <p>Returned model: {review.model ?? NOT_CAPTURED}</p>
                  <p className="tabular-nums">
                    Successful review call: {formatCount(review.input_tokens)} in / {formatCount(review.output_tokens)} out tokens ·{" "}
                    {formatMs(review.elapsed_ms)} · est. {formatUsd(review.cost_estimate_usd)}
                  </p>
                </>
              )}
            </>
          )}
        </Step>
        <Step
          state={checksFailed ? "failed" : generation.ran ? "done" : "skipped"}
          where="local"
          title="Citation, number, quotation, source-identity and review-integrity checks"
        >
          {turn.inspector.guard_errors.length > 0 && <p>Guard failures: {turn.inspector.guard_errors.join(", ")}</p>}
          {turn.inspector.integrity_errors.length > 0 && <p>Review-integrity failures: {turn.inspector.integrity_errors.join(", ")}</p>}
        </Step>
        <Step state="done" where="browser" title="Result returned to the browser">
          {turn.status === "answer"
            ? `Reviewed answer with ${turn.claims.length} claim(s) and ${turn.sources.length} saved source page(s).`
            : `${turn.status === "refusal" ? "Refusal" : "Clarification"} without source cards: ${turn.reason?.detail ?? "no reason recorded"}`}
        </Step>
      </ol>
      <LedgerSection window={turn.inspector.ledger_window} />
      <Section title="Timing (nested wall times)">
        <dl>
          <Row label="Server handler" value={formatMs(turn.timing.server_ms)} hint="Whole request on the server, including evidence validation" />
          <Row label="⤷ Shared answer call" value={formatMs(turn.timing.answer_call_ms)} hint="Measured by the bridge around parkguide.chat.answer" />
          <Row label="⤷ Pipeline, self-reported" value={formatMs(turn.timing.pipeline_ms)} hint="Includes retry waits and any first-use reranker load" />
          <Row label="⤷ Retrieval total" value={formatMs(retrieval.timings_ms.total_ms)} hint="Index load + scoring + rerank; excludes embedding" />
        </dl>
        <p className="text-xs text-pretty text-muted-foreground">
          Each row contains the rows below it. Per-call timings above are for successful calls only. “Not captured” means no value was recorded, which is
          different from zero.
        </p>
      </Section>
    </div>
    </HostedContext.Provider>
  )
}

export function Inspector({ turn }: { turn: ChatTurn | null }) {
  if (!turn) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-pretty text-muted-foreground">
        Ask a question, then open the inspector to see retrieval scores, review results and the data flow for that turn.
      </div>
    )
  }
  return (
    <Tabs defaultValue="evidence" className="flex h-full min-h-0 flex-col gap-0">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5">
        <TabsList>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="retrieval">Retrieval</TabsTrigger>
          <TabsTrigger value="flow">Data flow</TabsTrigger>
        </TabsList>
        <ExportButtons turn={turn} />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <p className="mb-4 line-clamp-2 text-xs text-pretty text-muted-foreground">“{turn.question}”</p>
        <TabsContent value="evidence">
          <EvidenceTab turn={turn} />
        </TabsContent>
        <TabsContent value="retrieval">
          <RetrievalTab turn={turn} />
        </TabsContent>
        <TabsContent value="flow">
          <DataFlowTab turn={turn} />
        </TabsContent>
      </div>
    </Tabs>
  )
}
