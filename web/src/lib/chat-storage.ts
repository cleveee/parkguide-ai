import { PARKS, validChatTurn, type ParkCode } from "./api.ts"
import type { TurnState } from "./use-chat"

export const LEGACY_CHAT_STORAGE_KEY = "parkguide.chat.v1"
export const CHAT_STORAGE_KEY = "parkguide.chat.v2"
export type Conversation = { id: string; park: ParkCode | null; turns: TurnState[] }
export type SavedChats = { version: 2; activeId: string; conversations: Conversation[] }

export const createConversation = (park: ParkCode | null): Conversation => ({ id: crypto.randomUUID(), park, turns: [] })
const empty = (): SavedChats => {
  const conversation = createConversation(null)
  return { version: 2, activeId: conversation.id, conversations: [conversation] }
}
const validPark = (park: unknown): park is ParkCode | null => park === null || PARKS.some((p) => p.code === park)
const record = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === "object" && !Array.isArray(value)

/** A request cannot resume when leaving its conversation or reloading. */
export const stopPendingTurns = (turns: TurnState[]): TurnState[] => turns.map((turn) => turn.phase === "pending"
  ? { id: turn.id, question: turn.question, park: turn.park, phase: "stopped" } : turn)

function readTurns(value: unknown, park: ParkCode | null): TurnState[] | null {
  if (!Array.isArray(value) || (park === null && value.length)) return null
  const ids = new Set<string>()
  const turns: TurnState[] = []
  for (const turn of value) {
    if (!record(turn) || typeof turn.id !== "string" || ids.has(turn.id) || typeof turn.question !== "string" || turn.park !== park) return null
    ids.add(turn.id)
    if (turn.phase === "done") {
      if (!validChatTurn(turn.response) || turn.response.selected_park !== park
        || typeof turn.clientMs !== "number" || !Number.isFinite(turn.clientMs)) return null
      turns.push(turn as TurnState)
    } else if (["pending", "stopped", "error"].includes(String(turn.phase)) && park !== null) {
      turns.push({ id: turn.id, question: turn.question, park, phase: "stopped" })
    } else return null
  }
  return turns
}

/** Validate browser data before it enters the renderer; migrate the prior single chat. */
export function loadChats(): SavedChats {
  try {
    const raw = window.localStorage.getItem(CHAT_STORAGE_KEY)
    if (raw !== null) {
      const saved: unknown = JSON.parse(raw)
      if (!record(saved) || saved.version !== 2 || typeof saved.activeId !== "string" || !Array.isArray(saved.conversations)) return empty()
      const ids = new Set<string>()
      const conversations: Conversation[] = []
      for (const item of saved.conversations) {
        if (!record(item) || typeof item.id !== "string" || ids.has(item.id) || !validPark(item.park)) return empty()
        const turns = readTurns(item.turns, item.park)
        if (!turns) return empty()
        ids.add(item.id)
        conversations.push({ id: item.id, park: item.park, turns })
      }
      if (!ids.has(saved.activeId)) return empty()
      return { version: 2, activeId: saved.activeId, conversations }
    }
    const legacy = window.localStorage.getItem(LEGACY_CHAT_STORAGE_KEY)
    if (!legacy) return empty()
    const saved: unknown = JSON.parse(legacy)
    if (!record(saved) || saved.version !== 1 || !validPark(saved.park)) return empty()
    const turns = readTurns(saved.turns, saved.park)
    if (!turns) return empty()
    const conversation = { ...createConversation(saved.park), turns }
    return { version: 2, activeId: conversation.id, conversations: [conversation] }
  } catch {
    return empty()
  }
}

export function saveChats(saved: SavedChats): boolean {
  try {
    window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(saved))
    // Only remove the old copy after the migrated collection is safely saved.
    window.localStorage.removeItem(LEGACY_CHAT_STORAGE_KEY)
    return true
  } catch {
    return false
  }
}

export function withActiveTurns(saved: SavedChats, turns: TurnState[]): SavedChats {
  return { ...saved, conversations: saved.conversations.map((chat) => chat.id === saved.activeId ? { ...chat, turns } : chat) }
}

export function startConversation(saved: SavedChats, turns: TurnState[], park: ParkCode | null): SavedChats {
  const snapshot = withActiveTurns(saved, stopPendingTurns(turns))
  const conversation = createConversation(park)
  return { version: 2, activeId: conversation.id, conversations: [conversation, ...snapshot.conversations] }
}

export function selectConversation(saved: SavedChats, turns: TurnState[], id: string): SavedChats {
  if (!saved.conversations.some((chat) => chat.id === id)) return saved
  return { ...withActiveTurns(saved, stopPendingTurns(turns)), activeId: id }
}
