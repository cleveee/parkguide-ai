import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react"
import { DatabaseIcon, InfoIcon, MenuIcon, MessageSquareIcon, PanelRightCloseIcon, PanelRightOpenIcon, PlusIcon, TreesIcon, XIcon } from "lucide-react"

import { PromptInputProvider } from "@/components/ai-elements/prompt-input"
import { ChatView } from "@/components/chat-view"
import { CorpusBrowser } from "@/components/corpus-browser"
import { EvidenceDialog } from "@/components/evidence-dialog"
import { HowItWorks } from "@/components/how-it-works"
import { Inspector } from "@/components/inspector"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { ResizableGroup, ResizablePanel, ResizeHandle } from "@/components/ui/resizable"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { ApiError, PARKS, getMeta, parkName, type Meta, type ParkCode } from "@/lib/api"
import { captureAge, formatDateTime } from "@/lib/format"
import { closeConversation, loadChats, saveChats, selectConversation, startConversation, withActiveTurns, type Conversation } from "@/lib/chat-storage"
import { useChat } from "@/lib/use-chat"
import { cn } from "@/lib/utils"

type View = "chat" | "corpus"
type PendingAction = { kind: "park"; park: ParkCode | null } | { kind: "new" } | { kind: "open"; id: string } | { kind: "close"; id: string }

const DESKTOP = "(min-width: 1280px)"
const WIDE = "(min-width: 768px)"

function useMediaQuery(query: string) {
  return useSyncExternalStore(
    (notify) => {
      const list = window.matchMedia(query)
      list.addEventListener("change", notify)
      return () => list.removeEventListener("change", notify)
    },
    () => window.matchMedia(query).matches,
  )
}

function Sidebar({
  id,
  park,
  view,
  meta,
  hasConversation,
  conversations,
  activeId,
  onOpen,
  onClose,
  onPark,
  onNew,
  onView,
  onAbout,
}: {
  id: string
  park: ParkCode | null
  view: View
  meta: Meta | null
  hasConversation: boolean
  conversations: Conversation[]
  activeId: string
  onOpen: (id: string) => void
  onClose: (id: string) => void
  onPark: (park: ParkCode | null) => void
  onNew: () => void
  onView: (view: View) => void
  onAbout: () => void
}) {
  const stats = meta?.parks.find((item) => item.code === park)
  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-4">
      <div className="flex items-center gap-2.5">
        <TreesIcon className="size-8 shrink-0 text-primary" aria-hidden />
        <div>
          <p className="text-sm font-semibold">ParkGuide</p>
          <p className="text-xs text-muted-foreground">Saved official NPS sources</p>
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor={`${id}-park`} className="text-xs font-medium text-muted-foreground">
          Park
        </label>
        <div className="flex min-w-0 items-center gap-1">
          <Select value={park ?? ""} onValueChange={(value) => onPark(value as ParkCode)}>
            <SelectTrigger
              id={`${id}-park`}
              className="min-w-0 flex-1 bg-background *:data-[slot=select-value]:block *:data-[slot=select-value]:min-w-0 *:data-[slot=select-value]:truncate"
              title={park ? `${parkName(park)} National Park` : "Choose a park"}
            >
              <SelectValue placeholder="Choose a park" />
            </SelectTrigger>
            <SelectContent>
              {PARKS.map((option) => (
                <SelectItem key={option.code} value={option.code}>
                  {option.name} National Park
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {park && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" className="shrink-0" aria-label="Clear selected park" onClick={() => onPark(null)}>
                  <XIcon />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Clear park</TooltipContent>
            </Tooltip>
          )}
        </div>
        {stats && (
          <p className="text-xs text-pretty text-muted-foreground" title={`Latest capture: ${formatDateTime(stats.captured_latest)}`}>
            <span className="tabular-nums">{stats.documents}</span> documents · {captureAge(stats.captured_latest) ?? "capture date unknown"}
          </p>
        )}
      </div>

      <nav className="space-y-1" aria-label="Main">
        <Button variant="outline" className="w-full justify-start bg-background" onClick={onNew} disabled={!park || !hasConversation}>
          <PlusIcon data-icon="inline-start" />
          New conversation
        </Button>
        <div className="h-2" />
        {(
          [
            { id: "chat", label: "Chat", icon: MessageSquareIcon },
            { id: "corpus", label: "Corpus", icon: DatabaseIcon },
          ] as const
        ).map((item) => (
          <Button
            key={item.id}
            variant="ghost"
            aria-current={view === item.id ? "page" : undefined}
            className={cn("w-full justify-start", view === item.id && "bg-sidebar-accent text-foreground")}
            onClick={() => onView(item.id)}
          >
            <item.icon data-icon="inline-start" />
            {item.label}
          </Button>
        ))}
        <Button variant="ghost" className="w-full justify-start" onClick={onAbout}>
          <InfoIcon data-icon="inline-start" />
          How it works
        </Button>
      </nav>

      <nav className="shrink-0 space-y-1" aria-label="Saved conversations">
        <p className="px-2 pb-1 text-xs font-medium text-muted-foreground">Your chats</p>
        {conversations.map((conversation) => (
          <div key={conversation.id} className={cn("flex items-center rounded-md", conversation.id === activeId && "bg-sidebar-accent")}>
            <Button variant="ghost" className="h-auto min-w-0 flex-1 justify-start px-2 py-2 text-left"
              aria-current={conversation.id === activeId ? "page" : undefined} onClick={() => onOpen(conversation.id)}
              title={conversation.turns[0]?.question ?? "New conversation"}>
              <MessageSquareIcon className="shrink-0" />
              <span className="min-w-0 flex-1">
                <span className="block truncate">{conversation.turns[0]?.question ?? "New conversation"}</span>
                <span className="block text-xs font-normal text-muted-foreground">{conversation.park ? parkName(conversation.park) : "Choose a park"}</span>
              </span>
            </Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" className="mr-1 shrink-0"
                  aria-label={`Close chat: ${conversation.turns[0]?.question ?? "New conversation"} (${conversation.park ? parkName(conversation.park) : "No park selected"})`}
                  onClick={() => onClose(conversation.id)}>
                  <XIcon />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Close chat</TooltipContent>
            </Tooltip>
          </div>
        ))}
      </nav>

      <p className="mt-auto text-xs text-pretty text-muted-foreground">
        Conversation history is saved in this browser and restored on reload. Saved pages are a snapshot, not live conditions.
      </p>
    </div>
  )
}

export default function App() {
  const [savedChats, setSavedChats] = useState(loadChats)
  const activeChat = savedChats.conversations.find((item) => item.id === savedChats.activeId)!
  const park = activeChat.park
  const [view, setView] = useState<View>("chat")
  const [meta, setMeta] = useState<Meta | null>(null)
  const [metaError, setMetaError] = useState<string | null>(null)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [inspectorTurnId, setInspectorTurnId] = useState<string | null>(null)
  const [evidence, setEvidence] = useState<{ turnId: string; number: number; claim: number | null } | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [aboutOpen, setAboutOpen] = useState(false)
  const [confirm, setConfirm] = useState<PendingAction | null>(null)
  const desktop = useMediaQuery(DESKTOP)
  // The sidebar is visible from Tailwind's md breakpoint, where the menu sheet is unnecessary.
  const wide = useMediaQuery(WIDE)
  const chat = useChat(park, activeChat.turns)
  const currentChats = useMemo(() => withActiveTurns(savedChats, chat.turns), [savedChats, chat.turns])
  const [storageFailed, setStorageFailed] = useState(false)
  useEffect(() => {
    const failed = !saveChats(currentChats)
    // This state reports the result of synchronizing with external browser storage.
    // oxlint-disable-next-line react/set-state-in-effect
    setStorageFailed(failed)
  }, [currentChats])

  const loadMeta = useCallback(() => {
    getMeta()
      .then((value) => {
        setMeta(value)
        setMetaError(null)
      })
      .catch((error) =>
        setMetaError(error instanceof ApiError ? `${error.message} (${error.code}${error.status ? `, HTTP ${error.status}` : ""})` : "Unknown client error."),
      )
  }, [])

  useEffect(() => {
    loadMeta()
  }, [loadMeta])

  const doneTurns = useMemo(() => chat.turns.flatMap((turn) => (turn.phase === "done" ? [turn] : [])), [chat.turns])
  const inspected = doneTurns.find((turn) => turn.id === inspectorTurnId) ?? doneTurns.at(-1) ?? null
  const evidenceTurn = doneTurns.find((turn) => turn.id === evidence?.turnId) ?? null

  const apply = (action: PendingAction) => {
    let next = savedChats
    if (action.kind === "close") {
      next = closeConversation(savedChats, chat.turns, action.id)
      if (action.id !== savedChats.activeId) {
        // Closing another chat must not interrupt this chat's reply or draft.
        setSavedChats(next)
        return
      }
    } else if (action.kind === "open") {
      next = selectConversation(savedChats, chat.turns, action.id)
    } else if (action.kind === "park" && chat.turns.length === 0) {
      next = { ...currentChats, conversations: currentChats.conversations.map((item) => item.id === currentChats.activeId ? { ...item, park: action.park } : item) }
    } else {
      next = startConversation(savedChats, chat.turns, action.kind === "park" ? action.park : park)
    }
    const selected = next.conversations.find((item) => item.id === next.activeId)!
    chat.replace(selected.turns)
    setSavedChats(next)
    setInspectorTurnId(null)
    setInspectorOpen(false)
    setEvidence(null)
    setView("chat")
    setMenuOpen(false)
  }

  const request = (action: PendingAction) => {
    if (action.kind === "park" && action.park === park) return
    if (action.kind === "open" && action.id === savedChats.activeId) {
      setView("chat")
      setMenuOpen(false)
      return
    }
    if (action.kind === "close" || chat.pending) {
      setMenuOpen(false)
      setConfirm(action)
    } else apply(action)
  }

  // One active modal layer. The dialogs below are opened by explicit user
  // actions; the two responsive sheets are derived and only mount when none
  // of them is open, so a breakpoint change can never stack a sheet on top of
  // (or behind) a visible dialog. The underlying inspectorOpen/menuOpen state
  // is kept, so the desktop side panel and the sheet resume afterwards.
  const evidenceShown = Boolean(evidence && evidenceTurn?.response.sources.some((page) => page.number === evidence.number))
  const dialogShown = evidenceShown || aboutOpen || Boolean(confirm)
  const menuSheetShown = menuOpen && !wide && !dialogShown
  const inspectorSheetShown = view === "chat" && !desktop && inspectorOpen && !dialogShown && !menuSheetShown

  const chatReady = meta?.chat.ready ?? false
  const sidebar = (id: string) => (
    <Sidebar
      id={id}
      park={park}
      view={view}
      meta={meta}
      hasConversation={chat.turns.length > 0}
      conversations={currentChats.conversations}
      activeId={savedChats.activeId}
      onOpen={(id) => request({ kind: "open", id })}
      onClose={(id) => request({ kind: "close", id })}
      onPark={(next) => request({ kind: "park", park: next })}
      onNew={() => request({ kind: "new" })}
      onView={(next) => {
        setView(next)
        setMenuOpen(false)
      }}
      onAbout={() => {
        setAboutOpen(true)
        setMenuOpen(false)
      }}
    />
  )

  const inspector = <Inspector turn={inspected?.response ?? null} />

  return (
    <TooltipProvider>
      <div className="flex h-dvh overflow-hidden bg-background pr-[env(safe-area-inset-right)] pl-[env(safe-area-inset-left)]">
        <ResizableGroup id="app-layout" orientation="horizontal" className="flex-1">
          {wide && (
            <ResizablePanel id="navigation" defaultSize="16rem" minSize="14.5rem" maxSize="22rem" groupResizeBehavior="preserve-pixel-size">
              <aside className="h-full overflow-y-auto bg-sidebar" aria-label="Navigation">{sidebar("sidebar")}</aside>
            </ResizablePanel>
          )}
          {wide && <ResizeHandle aria-label="Resize navigation sidebar" />}

          <ResizablePanel id="workspace" minSize={wide ? "30rem" : 0}>
            <div className="flex h-full min-w-0 flex-col">
              <header className="flex shrink-0 items-center gap-2 border-b px-3 pt-[env(safe-area-inset-top)] sm:px-4">
                <div className="flex h-13 min-w-0 flex-1 items-center gap-2">
                  <Button variant="ghost" size="icon-sm" className="md:hidden" aria-label="Open menu" onClick={() => setMenuOpen(true)}>
                    <MenuIcon />
                  </Button>
                  <div className="min-w-0">
                    <h1 className="truncate text-sm font-semibold">
                      {view === "corpus" ? "Saved corpus" : park ? `${parkName(park)} National Park` : "ParkGuide"}
                    </h1>
                    <p className="truncate text-xs text-muted-foreground">
                      {view === "corpus" ? "Read-only local database" : park ? "Answers use only this park's saved NPS sources" : "No park selected"}
                    </p>
                  </div>
                </div>
                {view === "chat" && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={inspectorOpen ? "Close inspector" : "Open inspector"}
                        aria-pressed={inspectorOpen}
                        onClick={() => setInspectorOpen((open) => !open)}
                      >
                        {inspectorOpen && desktop ? <PanelRightCloseIcon /> : <PanelRightOpenIcon />}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Inspector</TooltipContent>
                  </Tooltip>
                )}
              </header>

              {storageFailed && <p role="status" className="border-b px-4 py-2 text-sm">Browser storage is unavailable or full. Recent chat changes may be lost on reload.</p>}
              <div className="flex min-h-0 flex-1">
                <ResizableGroup id="conversation-layout" orientation="horizontal" className="flex-1">
                  <ResizablePanel id="conversation" minSize={desktop && inspectorOpen ? "30rem" : 0}>
                    <main className="flex h-full min-w-0 flex-col">
                      {view === "chat" ? (
                        <PromptInputProvider key={`${savedChats.activeId}-${park}`}>
                          <ChatView
                            park={park}
                            meta={meta}
                            metaError={metaError}
                            turns={chat.turns}
                            pending={chat.pending}
                            chatReady={chatReady}
                            onChoosePark={(next) => request({ kind: "park", park: next })}
                            onSend={chat.send}
                            onStop={chat.stopWaiting}
                            onReloadMeta={loadMeta}
                            onOpenEvidence={(turnId, number, claim) => setEvidence({ turnId, number, claim: claim ?? null })}
                            onInspect={(turnId) => {
                              setInspectorTurnId(turnId)
                              setInspectorOpen(true)
                            }}
                          />
                        </PromptInputProvider>
                      ) : (
                        <CorpusBrowser meta={meta} metaError={metaError} selectedPark={park} />
                      )}
                    </main>
                  </ResizablePanel>
                  {view === "chat" && desktop && inspectorOpen && (
                    <ResizeHandle aria-label="Resize inspector sidebar" />
                  )}
                  {view === "chat" && desktop && inspectorOpen && (
                    <ResizablePanel id="inspector" defaultSize="26rem" minSize="20rem" maxSize="35rem" groupResizeBehavior="preserve-pixel-size">
                      <aside className="flex h-full min-w-0 flex-col bg-card" aria-label="Inspector">
                        {inspector}
                      </aside>
                    </ResizablePanel>
                  )}
                </ResizableGroup>
              </div>
            </div>
          </ResizablePanel>
        </ResizableGroup>
      </div>

      <Sheet
        open={menuSheetShown}
        onOpenChange={(open) => {
          // Only a dismissal of the visible sheet changes state.
          if (!open && menuSheetShown) setMenuOpen(false)
        }}
      >
        <SheetContent side="left" className="bg-sidebar p-0 data-[side=left]:w-72">
          <SheetHeader className="sr-only">
            <SheetTitle>Menu</SheetTitle>
            <SheetDescription>Park selection and navigation</SheetDescription>
          </SheetHeader>
          {sidebar("menu")}
        </SheetContent>
      </Sheet>

      <Sheet
        open={inspectorSheetShown}
        onOpenChange={(open) => {
          // Only a dismissal of the visible sheet closes the inspector; a
          // breakpoint change or another dialog never clobbers inspectorOpen.
          if (!open && inspectorSheetShown) setInspectorOpen(false)
        }}
      >
        <SheetContent side="right" className="gap-0 p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-xl">
          <SheetHeader className="border-b pr-12">
            <SheetTitle>Inspector</SheetTitle>
            <SheetDescription>Evidence, retrieval and data flow for one turn.</SheetDescription>
          </SheetHeader>
          <div className="min-h-0 flex-1">{inspector}</div>
        </SheetContent>
      </Sheet>

      <EvidenceDialog
        response={evidenceTurn?.response ?? null}
        sourceNumber={evidence?.number ?? null}
        claimNumber={evidence?.claim ?? null}
        onOpenChange={(open) => !open && setEvidence(null)}
      />
      <HowItWorks open={aboutOpen} onOpenChange={setAboutOpen} meta={meta} />

      <AlertDialog open={Boolean(confirm)} onOpenChange={(open) => !open && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm?.kind === "close" ? "Close this chat?" : "Leave the reply in progress?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirm?.kind === "close" ? (
                <>This removes “{currentChats.conversations.find((item) => item.id === confirm.id)?.turns[0]?.question ?? "New conversation"}” and its messages and evidence from this browser’s saved chats. This cannot be undone.
                  {confirm.id === savedChats.activeId && chat.pending && " The pending reply will be ignored. The server may still finish the request, including any paid calls."}
                </>
              ) : (
                <>Your conversation and its evidence will remain in Your chats. The pending question will be marked stopped. The server may still finish the request (including paid calls), and a new question may get a “busy” reply until it finishes.</>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirm) apply(confirm)
                setConfirm(null)
              }}
            >
              {confirm?.kind === "close" ? "Close chat" : "Continue"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </TooltipProvider>
  )
}
