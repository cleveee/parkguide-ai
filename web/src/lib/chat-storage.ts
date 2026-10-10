import { PARKS, validChatTurn, type ParkCode } from "./api.ts"
import type { TurnState } from "./use-chat"

export const CHAT_STORAGE_KEY = "parkguide.chat.v1"
export type SavedChat = { version: 1; park: ParkCode | null; turns: TurnState[] }
const empty = (): SavedChat => ({ version: 1, park: null, turns: [] })

/** Untrusted browser data must pass the same response checks as network data. */
export function loadChat(): SavedChat {
  try {
    const raw = window.localStorage.getItem(CHAT_STORAGE_KEY)
    if (!raw) return empty()
    const saved = JSON.parse(raw)
    if (saved.version !== 1 || !(saved.park === null || PARKS.some((p) => p.code === saved.park))
      || !Array.isArray(saved.turns) || (saved.park === null && saved.turns.length)) return empty()
    const ids = new Set<string>()
    const turns: TurnState[] = []
    for (const turn of saved.turns) {
      if (!turn || typeof turn.id !== "string" || ids.has(turn.id) || typeof turn.question !== "string" || turn.park !== saved.park) return empty()
      ids.add(turn.id)
      if (turn.phase === "done") {
        if (!validChatTurn(turn.response) || turn.response.selected_park !== saved.park
          || typeof turn.clientMs !== "number" || !Number.isFinite(turn.clientMs)) return empty()
        turns.push(turn)
      } else if (["pending", "stopped", "error"].includes(turn.phase)) {
        // Requests cannot resume after reload. Keep the question without replaying it.
        turns.push({ id: turn.id, question: turn.question, park: turn.park, phase: "stopped" })
      } else return empty()
    }
    return { version: 1, park: saved.park, turns }
  } catch {
    return empty()
  }
}

export function saveChat(park: ParkCode | null, turns: TurnState[]): boolean {
  try {
    window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify({ version: 1, park, turns }))
    return true
  } catch {
    // Private browsing, blocked storage or quota limits must not break chatting.
    return false
  }
}
