import { useLayoutEffect, useRef, useState } from "react"
import { MapPinIcon, RotateCcwIcon, TreesIcon } from "lucide-react"

import { Conversation, ConversationContent, ConversationScrollButton } from "@/components/ai-elements/conversation"
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  usePromptInputController,
  type PromptInputMessage,
} from "@/components/ai-elements/prompt-input"
import { AssistantTurn, ErrorTurn, PendingTurn, StoppedTurn, UserTurn } from "@/components/assistant-turn"
import { Button } from "@/components/ui/button"
import { MAX_QUESTION_CHARS, PARKS, parkName, type Meta, type ParkCode } from "@/lib/api"
import { captureAge, formatCount, formatDateTime } from "@/lib/format"
import type { TurnState } from "@/lib/use-chat"

// Generic visitor questions written for this UI. They are not drawn from the
// gold or diagnostic evaluation sets and carry no expected answers.
const SUGGESTIONS: Record<ParkCode, string[]> = {
  yose: ["How should I store food overnight at a campground?", "Are pets allowed on trails?", "Can I fly a drone in the park?"],
  yell: ["How far should I stay from bison and elk?", "Can I swim in thermal features?", "Are pets allowed on boardwalks?"],
  grca: ["What should I bring for a day hike below the rim?", "Are pets allowed below the rim?", "Where can I refill water on the corridor trails?"],
}

function EmptyState({
  park,
  meta,
  metaError,
  onChoosePark,
  onSuggest,
}: {
  park: ParkCode | null
  meta: Meta | null
  metaError: string | null
  onChoosePark: (park: ParkCode) => void
  onSuggest: (question: string) => void
}) {
  if (!park) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-5 px-4 py-16 text-center">
        <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <TreesIcon className="size-5" aria-hidden />
        </span>
        <div className="space-y-1.5">
          <h2 className="text-lg font-semibold text-balance">Choose a park to start</h2>
          <p className="text-sm text-pretty text-muted-foreground">
            Answers come only from that park's saved official NPS pages, with every delivered claim checked against its cited passage.
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-2" role="group" aria-label="Choose a park">
          {PARKS.map((option) => (
            <Button key={option.code} variant="outline" onClick={() => onChoosePark(option.code)}>
              {option.name}
            </Button>
          ))}
        </div>
      </div>
    )
  }
  const stats = meta?.parks.find((item) => item.code === park)
  const age = captureAge(stats?.captured_latest)
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-5 px-4 py-16 text-center">
      <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <MapPinIcon className="size-5" aria-hidden />
      </span>
      <div className="space-y-1.5">
        <h2 className="text-lg font-semibold text-balance">Ask about visiting {parkName(park)}</h2>
        {stats ? (
          <p className="text-sm text-pretty text-muted-foreground">
            <span className="tabular-nums">{formatCount(stats.documents)}</span> saved NPS documents ·{" "}
            <span className="tabular-nums">{formatCount(stats.active_chunks)}</span> indexed passages
            {stats.captured_latest && (
              <>
                {" "}
                · snapshot {formatDateTime(stats.captured_latest)}
                {age && ` (${age})`}
              </>
            )}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">{metaError ? "Corpus details are unavailable right now." : "Loading corpus details…"}</p>
        )}
        <p className="text-xs text-pretty text-muted-foreground">Saved pages are a snapshot, not live conditions.</p>
      </div>
      <div className="flex w-full flex-col gap-2">
        {SUGGESTIONS[park].map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => onSuggest(question)}
            className="rounded-lg border bg-card px-3 py-2 text-left text-sm text-pretty text-foreground/85 transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  )
}

export function ChatView({
  park,
  meta,
  metaError,
  turns,
  pending,
  chatReady,
  onChoosePark,
  onSend,
  onStop,
  onReloadMeta,
  onOpenEvidence,
  onInspect,
}: {
  park: ParkCode | null
  meta: Meta | null
  metaError: string | null
  turns: TurnState[]
  pending: boolean
  chatReady: boolean
  onChoosePark: (park: ParkCode) => void
  onSend: (question: string) => Promise<{ ok: boolean; restore?: boolean }>
  onStop: () => void
  onReloadMeta: () => void
  onOpenEvidence: (turnId: string, sourceNumber: number, claimNumber?: number) => void
  onInspect: (turnId: string) => void
}) {
  const controller = usePromptInputController()
  const [notice, setNotice] = useState<string | null>(null)
  const value = controller.textInput.value
  const latestDraft = useRef(value)
  useLayoutEffect(() => { latestDraft.current = value }, [value])
  const tooLong = value.length > MAX_QUESTION_CHARS
  const disabled = !park || !chatReady

  const submit = (text: string) => {
    const question = text.trim()
    // Throwing keeps the composer text (upstream PromptInput clears only on success).
    if (!question || pending || disabled || question.length > MAX_QUESTION_CHARS) throw new Error("not sent")
    setNotice(null)
    void onSend(question).then((result) => {
      // Read the current draft after the request settles, not the value captured
      // when Send was clicked. Never overwrite a new question typed meanwhile.
      if (result.restore && !latestDraft.current) controller.textInput.setInput(question)
    })
  }

  const handleSubmit = (message: PromptInputMessage) => submit(message.text)

  const retry = (question: string) => {
    if (pending) return
    setNotice(null)
    void onSend(question)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Conversation className="min-h-0 flex-1" aria-label="Conversation">
        <ConversationContent className="mx-auto w-full max-w-3xl gap-6 px-4 py-6 sm:px-6">
          {turns.length === 0 ? (
            <EmptyState
              park={park}
              meta={meta}
              metaError={metaError}
              onChoosePark={onChoosePark}
              onSuggest={(question) => {
                controller.textInput.setInput(question)
                document.querySelector<HTMLTextAreaElement>("textarea[name=message]")?.focus()
              }}
            />
          ) : (
            turns.map((turn) => (
              <div key={turn.id} className="flex flex-col gap-4">
                <UserTurn question={turn.question} />
                {turn.phase === "pending" && <PendingTurn park={turn.park} onStop={onStop} />}
                {turn.phase === "stopped" && <StoppedTurn />}
                {turn.phase === "error" && <ErrorTurn turn={turn} canRetry={!pending} onRetry={() => retry(turn.question)} />}
                {turn.phase === "done" && (
                  <AssistantTurn
                    turn={turn}
                    onOpenEvidence={(number, claim) => onOpenEvidence(turn.id, number, claim)}
                    onInspect={() => onInspect(turn.id)}
                  />
                )}
                {turn.phase === "done" && turn.response.status === "answer" && turn.id === turns.at(-1)?.id && !pending
                  && Boolean(turn.response.suggested_questions?.length) && (
                  <div className="space-y-2" role="group" aria-label="Suggested follow-up questions">
                    <p className="text-xs font-medium text-muted-foreground">Explore next</p>
                    {turn.response.suggested_questions?.slice(0, 3).map((suggestion) => (
                      <Button key={suggestion.id} variant="outline" disabled={disabled}
                        className="h-auto w-full justify-start py-2 text-left whitespace-normal" onClick={() => {
                          controller.textInput.setInput(suggestion.question)
                          document.querySelector<HTMLTextAreaElement>("textarea[name=message]")?.focus()
                        }}>
                        {suggestion.question}
                      </Button>
                    ))}
                    <p className="text-xs text-muted-foreground">Choose a question to edit and send. Based on saved NPS sources.</p>
                  </div>
                )}
              </div>
            ))
          )}
        </ConversationContent>
        <ConversationScrollButton aria-label="Scroll to latest message" />
      </Conversation>

      <div className="border-t bg-background/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6">
        <div className="mx-auto w-full max-w-3xl">
          <PromptInput onSubmit={handleSubmit} maxFiles={0} onError={() => setNotice("Attachments are not supported. Paste text only.")}>
            <PromptInputBody>
              <PromptInputTextarea
                aria-label={park ? `Question about ${parkName(park)}` : "Question (choose a park first)"}
                placeholder={!park ? "Choose a park to start" : !chatReady ? "Chat is unavailable" : `Ask about visiting ${parkName(park)}…`}
                disabled={disabled}
                className="text-[0.938rem]"
              />
            </PromptInputBody>
            <PromptInputFooter>
              <PromptInputTools className="gap-2 text-xs text-muted-foreground">
                {park ? (
                  <span className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-1 font-medium text-primary">
                    <MapPinIcon className="size-3" aria-hidden />
                    {parkName(park)} National Park
                  </span>
                ) : (
                  <span>No park selected</span>
                )}
                <span className="hidden sm:inline">Enter to send · Shift+Enter for a new line</span>
              </PromptInputTools>
              <div className="flex items-center gap-2">
                {(tooLong || value.length > MAX_QUESTION_CHARS - 100) && (
                  <span className={tooLong ? "text-xs text-destructive tabular-nums" : "text-xs text-muted-foreground tabular-nums"}>
                    {value.length}/{MAX_QUESTION_CHARS}
                  </span>
                )}
                {/* Send only. While a reply is pending the button is disabled; the
                    explicitly labelled "Stop waiting" control in the conversation is
                    the only way to stop waiting. */}
                <PromptInputSubmit
                  status="ready"
                  disabled={pending || disabled || !value.trim() || tooLong}
                  aria-label={pending ? "Send question (disabled while a reply is pending)" : "Send question"}
                />
              </div>
            </PromptInputFooter>
          </PromptInput>
          <div className="mt-2 flex min-h-4 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-pretty text-muted-foreground" aria-live="polite">
            {notice ? (
              <span>{notice}</span>
            ) : metaError ? (
              <>
                <span className="text-destructive">Chat is unavailable because server metadata could not be loaded: {metaError}</span>
                <Button variant="outline" size="xs" onClick={onReloadMeta}>
                  <RotateCcwIcon data-icon="inline-start" />
                  Reload metadata
                </Button>
              </>
            ) : !meta ? (
              <span>Loading server metadata…</span>
            ) : !chatReady ? (
              <span>
                Chat is unavailable: the server reports{" "}
                <code className="font-mono">{meta.chat.reason ?? "not ready (no reason given)"}</code>.
              </span>
            ) : (
              <span>Answers rely on an AI source review of saved NPS pages; check official information for safety-critical decisions.</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
