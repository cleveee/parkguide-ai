import { useEffect, useState } from "react"
import { ChevronDownIcon, CircleAlertIcon, CircleHelpIcon, ExternalLinkIcon, PanelRightIcon, RotateCcwIcon, ShieldCheckIcon } from "lucide-react"
import { motion, useReducedMotion } from "motion/react"

import { Message, MessageAction, MessageActions, MessageContent } from "@/components/ai-elements/message"
import { Sources, SourcesContent, SourcesTrigger } from "@/components/ai-elements/sources"
import { SourceCard } from "@/components/source-card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { parkName, type ChatTurn, type LedgerWindow, type ReasonCategory } from "@/lib/api"
import { formatMs, formatUsd } from "@/lib/format"
import type { TurnState } from "@/lib/use-chat"

function Appear({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion()
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  )
}

function StatusLine({ response }: { response: ChatTurn }) {
  const withheld = response.inspector.review.withheld_claims ?? 0
  if (response.status === "answer") {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <ShieldCheckIcon className="size-3.5 text-primary" aria-hidden />
        <span>
          AI-checked against saved NPS sources
          {withheld > 0 && ` · ${withheld} unsupported ${withheld === 1 ? "claim" : "claims"} withheld`}
        </span>
      </p>
    )
  }
  if (response.status === "clarification") {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <CircleHelpIcon className="size-3.5" aria-hidden />
        A little more detail will help
      </p>
    )
  }
  return (
    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <CircleAlertIcon className="size-3.5" aria-hidden />
      {REFUSAL_LABELS[response.reason?.category ?? "model_refusal"]}
    </p>
  )
}

const REFUSAL_LABELS: Record<ReasonCategory, string> = {
  local_preflight: "This needs a different source",
  scope_check: "I couldn't verify the sources for this park",
  validation_failure: "I couldn't verify an answer",
  review_failure: "The source check couldn't finish",
  review_rejected: "I couldn't confirm the answer from the saved sources",
  no_evidence: "No matching information in the saved sources",
  model_refusal: "Not enough information in the saved sources",
  model_clarification: "A little more detail will help",
}

function LedgerNote({ window }: { window: LedgerWindow | undefined }) {
  if (!window) return null
  if (!window.captured) return <p className="text-xs text-muted-foreground">Paid-call ledger for this request: not captured.</p>
  return (
    <p className="text-xs text-pretty text-muted-foreground tabular-nums">
      Paid-call ledger during this request: {window.events} recorded {window.events === 1 ? "event" : "events"}, est. {formatUsd(window.cost_estimate_usd)}
      {window.includes_reserved_maximums && " (includes reserved maximums for calls without reported usage)"}.
    </p>
  )
}

export function UserTurn({ question }: { question: string }) {
  return (
    <Message from="user">
      <MessageContent>
        <p className="whitespace-pre-wrap text-pretty [overflow-wrap:anywhere]">{question}</p>
      </MessageContent>
    </Message>
  )
}

export function PendingTurn({ park, onStop }: { park: string; onStop: () => void }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [])
  return (
    <Message from="assistant">
      <MessageContent className="w-full max-w-xl gap-3">
        <div role="status" aria-live="polite" className="flex items-center gap-2 text-muted-foreground">
          <Spinner />
          <span>{seconds >= 20 ? "Still checking the saved sources…" : `Looking up your question in saved ${parkName(park)} sources…`}</span>
        </div>
        <div className="space-y-2" aria-hidden>
          <Skeleton className="h-3 w-11/12" />
          <Skeleton className="h-3 w-9/12" />
          <Skeleton className="h-3 w-7/12" />
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="text-pretty">{seconds >= 20 ? "This is taking longer than usual. You can stop waiting below." : "The answer appears after its source check."}</span>
          <span className="tabular-nums" aria-label={`${seconds} seconds elapsed`}>{seconds}s</span>
          <Button variant="outline" size="xs" onClick={onStop} title="Stops this browser from waiting; the server keeps working on the request">
            Stop waiting
          </Button>
        </div>
      </MessageContent>
    </Message>
  )
}

export function StoppedTurn() {
  return (
    <Message from="assistant">
      <MessageContent>
        <p className="text-xs text-pretty text-muted-foreground">
          You stopped waiting. The server may still finish this request, including any paid model calls; its reply will not be shown. Until it finishes, a
          new question gets a “busy” reply.
        </p>
      </MessageContent>
    </Message>
  )
}

// Repeating these gives the same result (validation, budget, configuration or
// local-state failures), so no Retry is offered.
const DETERMINISTIC_ERRORS = new Set([
  "invalid_request",
  "question_too_long_for_reranker",
  "budget_exhausted",
  "pricing_missing",
  "model_not_configured",
  "embedding_not_configured",
  "azure_configuration_mismatch",
  "embedding_cache_integrity_failed",
  "local_resource_unavailable",
  "chat_unavailable",
  "database_missing",
  "index_missing",
  "index_not_structure",
  "index_incomplete",
  "host_not_allowed",
  "origin_not_allowed",
  "json_required",
  "body_too_large",
])

export function ErrorTurn({ turn, onRetry, canRetry }: { turn: Extract<TurnState, { phase: "error" }>; onRetry: () => void; canRetry: boolean }) {
  const { code, message, details } = turn.error
  const retryable = !DETERMINISTIC_ERRORS.has(code)
  // A 409 means this request never started; anything else may have reached Azure.
  const mayBill = code !== "busy" && retryable
  return (
    <Message from="assistant">
      <Alert variant="destructive" className="max-w-xl">
        <CircleAlertIcon />
        <AlertTitle>{code === "busy" ? "Server busy: this question was not processed" : "Request failed: no answer was produced"}</AlertTitle>
        <AlertDescription className="[overflow-wrap:anywhere]">
          <p className="text-pretty">{message}</p>
          <LedgerNote window={details?.ledger_window} />
          {!details?.ledger_window && code !== "busy" && (
            <p className="text-xs text-pretty text-muted-foreground">
              No usage record was returned for this request; its cost is unknown here.
            </p>
          )}
          {retryable ? (
            <div className="mt-2 space-y-1">
              {mayBill && (
                <p className="text-xs text-pretty">Retrying sends the question again and can make new paid Azure calls on top of any already recorded.</p>
              )}
              <Button variant="outline" size="xs" onClick={onRetry} disabled={!canRetry}>
                <RotateCcwIcon data-icon="inline-start" />
                {mayBill ? "Retry (may spend again)" : "Retry"}
              </Button>
            </div>
          ) : (
            <p className="mt-1 text-xs text-pretty text-muted-foreground">Retrying would fail the same way, so no retry is offered.</p>
          )}
        </AlertDescription>
      </Alert>
    </Message>
  )
}

export function AssistantTurn({
  turn,
  onOpenEvidence,
  onInspect,
}: {
  turn: Extract<TurnState, { phase: "done" }>
  onOpenEvidence: (sourceNumber: number, claimNumber?: number) => void
  onInspect: () => void
}) {
  const response = turn.response
  return (
    <Appear>
      <Message from="assistant">
        <MessageContent className="w-full max-w-2xl gap-3">
          <StatusLine response={response} />
          {response.status === "answer" ? (
            <div className="space-y-2 text-[0.938rem] leading-relaxed">
              {response.claims.map((claim) => (
                <p key={claim.number} className="text-pretty [overflow-wrap:anywhere]">
                  {claim.text}
                  {claim.source_numbers.map((number) => (
                    <button
                      key={number}
                      type="button"
                      onClick={() => onOpenEvidence(number, claim.number)}
                      className="ml-1 inline-flex h-4.5 min-w-4.5 translate-y-[-1px] items-center justify-center rounded bg-primary/10 px-1 align-middle text-[0.688rem] font-medium tabular-nums text-primary hover:bg-primary/20 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                      aria-label={`Open saved evidence for source ${number}`}
                    >
                      {number}
                    </button>
                  ))}
                </p>
              ))}
            </div>
          ) : (
            <div className="space-y-1.5">
              <p className="text-[0.938rem] leading-relaxed text-pretty">{response.text}</p>
              {response.status === "refusal" && response.reason?.code !== "selected_park_mismatch" && (
                <a
                  href={`https://www.nps.gov/${response.selected_park}/planyourvisit/${["live_information_unavailable", "dated_information_unavailable"].includes(response.reason?.code ?? "") ? "conditions" : "index"}.htm`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {["live_information_unavailable", "dated_information_unavailable"].includes(response.reason?.code ?? "") ? "Check current NPS alerts and conditions" : `Visit official ${parkName(response.selected_park)} information`}
                  <ExternalLinkIcon className="size-3.5" aria-hidden />
                </a>
              )}
            </div>
          )}
          {response.history.scope_reset && (
            <p className="text-xs text-pretty text-muted-foreground">
              Messages about another park were excluded. {response.history.messages_used} of {response.history.messages_received} prior messages remain in context.
            </p>
          )}
          {response.sources.length > 0 && (
            <Sources className="mb-0">
              <SourcesTrigger count={response.sources.length} className="group rounded-md text-xs font-medium text-primary hover:underline">
                <span>
                  Sources used · {response.sources.length} saved {response.sources.length === 1 ? "page" : "pages"}
                </span>
                <ChevronDownIcon className="size-3.5 transition-transform group-data-[state=open]:rotate-180" aria-hidden />
              </SourcesTrigger>
              <SourcesContent className="w-full">
                {response.sources.map((page) => (
                  <SourceCard key={page.number} page={page} onOpen={() => onOpenEvidence(page.number)} />
                ))}
              </SourcesContent>
            </Sources>
          )}
        </MessageContent>
        <MessageActions className="text-xs text-muted-foreground">
          <span className="tabular-nums" title="Measured in this browser, request to reply">
            {formatMs(turn.clientMs)}
          </span>
          <MessageAction tooltip="Inspect retrieval and data flow" label="Inspect this turn" onClick={onInspect}>
            <PanelRightIcon />
          </MessageAction>
        </MessageActions>
      </Message>
    </Appear>
  )
}
