import { useCallback, useRef, useState } from "react"

import {
  ApiError,
  MAX_HISTORY_CONTENT_CHARS,
  MAX_HISTORY_MESSAGES,
  postChat,
  type ChatTurn,
  type ErrorDetails,
  type HistoryMessage,
  type ParkCode,
} from "@/lib/api"

export type TurnState =
  | { id: string; question: string; park: ParkCode; phase: "pending"; startedAt: number }
  | { id: string; question: string; park: ParkCode; phase: "done"; response: ChatTurn; clientMs: number }
  | {
      id: string
      question: string
      park: ParkCode
      phase: "error"
      error: { status: number; code: string; message: string; details: ErrorDetails | null }
    }
  | { id: string; question: string; park: ParkCode; phase: "stopped" }

let counter = 0
const nextId = () => `turn-${Date.now().toString(36)}-${(counter++).toString(36)}`

/** Conversation history lives only in this browser tab's memory. */
export function useChat(park: ParkCode | null) {
  const [turns, setTurns] = useState<TurnState[]>([])
  const [pending, setPending] = useState(false)
  // Every reset bumps the epoch; replies from an older epoch are discarded.
  const epoch = useRef(0)
  const inflight = useRef<{ controller: AbortController; turnId: string } | null>(null)

  const reset = useCallback(() => {
    epoch.current += 1
    inflight.current?.controller.abort()
    inflight.current = null
    setPending(false)
    setTurns([])
  }, [])

  const stopWaiting = useCallback(() => {
    const current = inflight.current
    if (!current) return
    epoch.current += 1
    current.controller.abort()
    inflight.current = null
    setPending(false)
    setTurns((all) => all.map((turn) => (turn.id === current.turnId ? { id: turn.id, question: turn.question, park: turn.park, phase: "stopped" } : turn)))
  }, [])

  const send = useCallback(
    async (question: string): Promise<{ ok: boolean; restore?: boolean }> => {
      if (!park || inflight.current) return { ok: false }
      const history: HistoryMessage[] = []
      for (const turn of turns) {
        if (turn.phase !== "done" || turn.park !== park) continue
        // An other-park question was refused locally; leave that exchange out
        // of the selected park's follow-up context.
        if (turn.response.reason?.code === "selected_park_mismatch") continue
        // The server rejects blank history content, so a pair with empty text
        // would make every later request fail; skip the whole pair.
        if (!turn.question.trim() || !turn.response.history_content.trim()) continue
        history.push({ role: "user", content: turn.question.slice(0, MAX_HISTORY_CONTENT_CHARS) })
        history.push({ role: "assistant", content: turn.response.history_content.slice(0, MAX_HISTORY_CONTENT_CHARS),
          ...(turn.response.history_evidence_ids?.length ? { evidence_ids: turn.response.history_evidence_ids } : {}) })
      }
      const bounded = history.slice(-MAX_HISTORY_MESSAGES)
      const id = nextId()
      const controller = new AbortController()
      const myEpoch = epoch.current
      const started = performance.now()
      inflight.current = { controller, turnId: id }
      setPending(true)
      setTurns((all) => [...all, { id, question, park, phase: "pending", startedAt: Date.now() }])
      try {
        const response = await postChat({ selected_park: park, question, history: bounded }, controller.signal)
        if (epoch.current !== myEpoch) return { ok: false }
        if (response.selected_park !== park) {
          // Never show a reply for another park, and never leave the turn pending.
          const info = {
            status: 0,
            code: "response_park_mismatch",
            message: `The server replied for ${response.selected_park}, not the selected park, so the reply was discarded.`,
            details: { ledger_window: response.inspector?.ledger_window },
          }
          setTurns((all) => all.map((turn) => (turn.id === id ? { id, question, park, phase: "error", error: info } : turn)))
          return { ok: false }
        }
        const clientMs = performance.now() - started
        setTurns((all) => all.map((turn) => (turn.id === id ? { id, question, park, phase: "done", response, clientMs } : turn)))
        return { ok: true }
      } catch (error) {
        if (epoch.current !== myEpoch) return { ok: false }
        const info =
          error instanceof ApiError
            ? { status: error.status, code: error.code, message: error.message, details: error.details }
            : { status: 0, code: "client_error", message: "The request could not be completed.", details: null }
        setTurns((all) => all.map((turn) => (turn.id === id ? { id, question, park, phase: "error", error: info } : turn)))
        return { ok: false, restore: true }
      } finally {
        if (epoch.current === myEpoch) {
          inflight.current = null
          setPending(false)
        }
      }
    },
    [park, turns],
  )

  return { turns, pending, send, reset, stopWaiting }
}
