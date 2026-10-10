import { useEffect, useState } from "react"
import { ChevronLeftIcon, ChevronRightIcon, ExternalLinkIcon, SearchIcon, TableIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  ApiError,
  PARKS,
  getDocument,
  getPassages,
  listDocuments,
  parkName,
  type DocumentDetail,
  type DocumentList,
  type Meta,
  type ParkCode,
  type PassageList,
} from "@/lib/api"
import { captureAge, formatCount, formatDate, formatDateTime, pageTypeLabel } from "@/lib/format"
import { cn } from "@/lib/utils"

const PAGE_SIZE = 25

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

function Overview({ meta, scope }: { meta: Meta; scope: ParkCode | "all" }) {
  const park = scope === "all" ? null : meta.parks.find((item) => item.code === scope)
  const documents = park ? park.documents : meta.totals.documents
  const html = park ? park.html : meta.totals.html
  const pdf = park ? park.pdf : meta.totals.pdf
  const tables = park ? park.table_documents : meta.totals.table_documents
  const activeChunks = park ? park.active_chunks : meta.active_build?.chunk_count ?? 0
  const latest = park ? park.captured_latest : meta.parks.map((item) => item.captured_latest).filter(Boolean).sort().at(-1)
  return (
    <div className="space-y-4">
      <section className="rounded-lg border bg-card p-4">
        <h3 className="text-sm font-medium">{park ? `${park.name} · stored documents` : "All parks · stored documents"}</h3>
        <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-5">
          <Stat label="Documents" value={formatCount(documents)} />
          <Stat label="HTML" value={formatCount(html)} />
          <Stat label="PDF" value={formatCount(pdf)} />
          <Stat label="With tables" value={formatCount(tables)} />
          <Stat label="Active-build passages" value={formatCount(activeChunks)} />
        </dl>
        <p className="mt-3 text-xs text-pretty text-muted-foreground">
          Latest capture {formatDateTime(latest ?? null)}
          {captureAge(latest ?? null) && ` (${captureAge(latest ?? null)})`}. Passages count only the active structure build
          {park ? ` for ${park.name}` : ""}.
        </p>
      </section>
      <section className="rounded-lg border bg-card">
        <div className="flex flex-wrap items-baseline justify-between gap-2 px-4 pt-3">
          <h3 className="text-sm font-medium">All stored chunk builds</h3>
          <p className="text-xs text-muted-foreground tabular-nums">
            {formatCount(meta.totals.chunks_all_builds)} chunks · {formatCount(meta.totals.vectors_all_builds)} vectors across all parks
          </p>
        </div>
        <div className="overflow-x-auto p-2">
          <Table className="text-xs">
            <TableHeader>
              <TableRow>
                <TableHead>Build</TableHead>
                <TableHead>Strategy</TableHead>
                <TableHead className="text-right">Chunks</TableHead>
                <TableHead className="text-right">Vectors</TableHead>
                <TableHead className="text-right">Dimensions</TableHead>
                <TableHead>Embedding</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {meta.builds.map((build) => (
                <TableRow key={build.build_id}>
                  <TableCell className="font-mono">
                    {build.build_id.slice(0, 12)}
                    {build.active && (
                      <Badge className="ml-2" variant="secondary">
                        Active · used by chat
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{build.strategy ?? "unknown"}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatCount(build.chunk_count)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatCount(build.vector_count)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatCount(build.dimension)}</TableCell>
                  <TableCell>{build.embedding_deployment ?? "unknown"}</TableCell>
                  <TableCell className="tabular-nums">{formatDate(build.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  )
}

function DocumentSheet({ docId, onOpenChange }: { docId: string | null; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={Boolean(docId)} onOpenChange={onOpenChange}>
      {/* The data-[side=right] variant is needed to override the primitive's sm:max-w-sm. */}
      <SheetContent className="gap-0 data-[side=right]:w-full data-[side=right]:sm:max-w-xl">
        {docId && <DocumentBody key={docId} docId={docId} />}
      </SheetContent>
    </Sheet>
  )
}

// Keyed by document ID, so pagination state starts fresh for each document.
function DocumentBody({ docId }: { docId: string }) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [passages, setPassages] = useState<PassageList | null>(null)
  const [blockOffset, setBlockOffset] = useState(0)
  const [passageOffset, setPassageOffset] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    getDocument(docId, blockOffset, 20)
      .then((value) => {
        if (!live) return
        setDetail(value)
        setError(null)
      })
      .catch((reason) => live && setError(reason instanceof ApiError ? reason.message : "Could not load this document."))
    return () => {
      live = false
    }
  }, [docId, blockOffset])

  useEffect(() => {
    let live = true
    getPassages(docId, passageOffset, 10)
      .then((value) => live && setPassages(value))
      .catch((reason) => live && setError(reason instanceof ApiError ? reason.message : "Could not load passages."))
    return () => {
      live = false
    }
  }, [docId, passageOffset])

  const current = detail
  const currentPassages = passages
  return (
    <>
        <SheetHeader className="border-b pr-12">
          <SheetTitle className="text-balance">{current?.title ?? "Stored document"}</SheetTitle>
          <SheetDescription asChild>
            <div className="space-y-1 text-xs">
              {current && (
                <>
                  <p>
                    {parkName(current.park)} · {pageTypeLabel(current.page_type)}
                    {current.has_table && " · contains tables"} · Source date {current.effective_date ?? "not stated"} · Saved{" "}
                    <span title={current.crawled_at ?? undefined}>{formatDateTime(current.crawled_at)}</span>
                  </p>
                  {current.source_url && (
                    <a
                      className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                      href={current.source_url}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      Current official NPS page
                      <ExternalLinkIcon className="size-3" aria-hidden />
                    </a>
                  )}
                </>
              )}
            </div>
          </SheetDescription>
        </SheetHeader>
        {error && <p className="px-4 pt-3 text-sm text-destructive">{error}</p>}
        {!current && !error && (
          <div className="space-y-2 p-4">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        )}
        {current && (
          <Tabs defaultValue="sections" className="flex min-h-0 flex-1 flex-col gap-0">
            <div className="border-b px-4 py-2">
              <TabsList>
                <TabsTrigger value="sections">
                  Sections <span className="text-muted-foreground tabular-nums">{formatCount(current.block_count)}</span>
                </TabsTrigger>
                <TabsTrigger value="passages">
                  Indexed passages <span className="text-muted-foreground tabular-nums">{formatCount(currentPassages?.total ?? null)}</span>
                </TabsTrigger>
                <TabsTrigger value="details">Details</TabsTrigger>
              </TabsList>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4 text-sm">
            <TabsContent value="details">
              <section className="space-y-2">
                <h3 className="text-xs font-medium">Chunks stored for this document</h3>
                <ul className="space-y-1 text-xs">
                  {current.chunks_by_build.map((build) => (
                    <li key={build.build_id} className="flex justify-between gap-2">
                      <span>
                        {build.strategy ?? "unknown"} build <span className="font-mono text-muted-foreground">{build.build_id.slice(0, 12)}</span>
                        {build.active && " · active"}
                      </span>
                      <span className="tabular-nums">{formatCount(build.chunks)}</span>
                    </li>
                  ))}
                </ul>
                <p className="font-mono text-[0.688rem] break-all text-muted-foreground">content sha256 {current.content_hash}</p>
                <p className="text-xs text-muted-foreground">Captured {formatDateTime(current.crawled_at)} ({current.crawled_at ?? "no timestamp"})</p>
              </section>
            </TabsContent>

            <TabsContent value="sections">
              <section className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs font-medium text-muted-foreground">Stored normalized text, in document order</h3>
                  <Pager offset={blockOffset} limit={20} total={current.block_count} onChange={setBlockOffset} label="sections" />
                </div>
                <ol className="space-y-3">
                  {current.sections.map((section) => (
                    <li key={section.index} className="space-y-1 rounded-md border bg-card p-2.5">
                      <p className="text-xs text-muted-foreground">
                        {section.heading_path || "No heading"} · {section.kind}
                        {section.start !== null && <span className="tabular-nums"> · offsets {section.start}–{section.end}</span>}
                      </p>
                      <p className={cn("text-xs whitespace-pre-wrap text-pretty", section.kind === "table" && "font-mono")}>
                        {section.text}
                        {section.truncated && "…"}
                      </p>
                    </li>
                  ))}
                </ol>
              </section>
            </TabsContent>

            <TabsContent value="passages">
              <section className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs font-medium text-muted-foreground">Active structure build, in document order</h3>
                  {currentPassages && (
                    <Pager offset={passageOffset} limit={10} total={currentPassages.total} onChange={setPassageOffset} label="passages" />
                  )}
                </div>
                <ol className="space-y-3">
                  {currentPassages?.passages.map((passage) => (
                    <li key={passage.chunk_id} className="space-y-1 rounded-md border bg-card p-2.5">
                      <p className="text-xs text-muted-foreground">
                        <span className="tabular-nums">#{passage.position}</span> · {passage.heading_path || "No heading"} ·{" "}
                        <span className="tabular-nums">{passage.token_count} tokens</span>
                      </p>
                      <p className="text-xs whitespace-pre-wrap text-pretty">{passage.text}</p>
                      <p className="font-mono text-[0.688rem] text-muted-foreground">{passage.chunk_id.slice(0, 12)}</p>
                    </li>
                  ))}
                </ol>
              </section>
            </TabsContent>
            </div>
          </Tabs>
        )}
    </>
  )
}

function Pager({ offset, limit, total, onChange, label }: { offset: number; limit: number; total: number; onChange: (offset: number) => void; label: string }) {
  if (total <= limit) return null
  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground">
      <span className="tabular-nums">
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <Button variant="ghost" size="icon-xs" aria-label={`Previous ${label}`} disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
        <ChevronLeftIcon />
      </Button>
      <Button variant="ghost" size="icon-xs" aria-label={`Next ${label}`} disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>
        <ChevronRightIcon />
      </Button>
    </div>
  )
}

export function CorpusBrowser({ meta, metaError, selectedPark }: { meta: Meta | null; metaError: string | null; selectedPark: ParkCode | null }) {
  const [scope, setScope] = useState<ParkCode | "all">(selectedPark ?? "all")
  const [query, setQuery] = useState("")
  const [debounced, setDebounced] = useState("")
  const [type, setType] = useState("any")
  const [tables, setTables] = useState("any")
  const [offset, setOffset] = useState(0)
  const [list, setList] = useState<DocumentList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openDoc, setOpenDoc] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(query.trim())
      setOffset(0)
    }, 250)
    return () => window.clearTimeout(timer)
  }, [query])

  // Changing any filter returns to the first page.
  const filter = <T,>(set: (value: T) => void) => (value: T) => {
    set(value)
    setOffset(0)
  }

  useEffect(() => {
    const controller = new AbortController()
    listDocuments(
      {
        park: scope === "all" ? undefined : scope,
        q: debounced || undefined,
        page_type: type === "any" ? undefined : type,
        has_table: tables === "any" ? undefined : tables === "yes",
        offset,
        limit: PAGE_SIZE,
      },
      controller.signal,
    )
      .then((value) => {
        setList(value)
        setError(null)
      })
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return
        setError(reason instanceof ApiError ? reason.message : "Could not load documents.")
      })
    return () => controller.abort()
  }, [scope, debounced, type, tables, offset])

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-6">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-balance">Saved corpus</h2>
          <p className="text-sm text-pretty text-muted-foreground">
            Read-only view of the local SQLite database. Previews show stored text; links go to the current official NPS pages.
          </p>
        </div>

        <Tabs value={scope} onValueChange={(value) => filter(setScope)(value as ParkCode | "all")}>
          <TabsList>
            <TabsTrigger value="all">All parks</TabsTrigger>
            {PARKS.map((park) => (
              <TabsTrigger key={park.code} value={park.code}>
                {park.name}
                {park.code === selectedPark && <span className="sr-only"> (selected for chat)</span>}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        {selectedPark && scope !== selectedPark && (
          <p className="-mt-3 text-xs text-muted-foreground">Chat is currently scoped to {parkName(selectedPark)}.</p>
        )}

        {meta ? <Overview meta={meta} scope={scope} /> : <p className="text-sm text-muted-foreground">{metaError ?? "Loading corpus metadata…"}</p>}

        <section className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-48 flex-1">
              <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value.slice(0, 100))}
                placeholder="Search titles and URLs"
                aria-label="Search stored documents by title or URL"
                className="pl-8"
              />
            </div>
            <Select value={type} onValueChange={filter(setType)}>
              <SelectTrigger aria-label="Filter by file type" className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">Any type</SelectItem>
                <SelectItem value="html">HTML</SelectItem>
                <SelectItem value="pdf">PDF</SelectItem>
              </SelectContent>
            </Select>
            <Select value={tables} onValueChange={filter(setTables)}>
              <SelectTrigger aria-label="Filter by table content" className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">Tables: any</SelectItem>
                <SelectItem value="yes">With tables</SelectItem>
                <SelectItem value="no">Without tables</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="overflow-x-auto rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  <TableHead>Park</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Passages</TableHead>
                  <TableHead>Captured</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list?.items.map((doc) => (
                  <TableRow key={doc.doc_id}>
                    <TableCell className="max-w-md whitespace-normal">
                      <button
                        type="button"
                        className="text-left font-medium text-pretty hover:text-primary hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                        onClick={() => setOpenDoc(doc.doc_id)}
                      >
                        {doc.title}
                      </button>
                      <p className="truncate text-xs text-muted-foreground">{doc.source_url?.replace("https://www.nps.gov", "")}</p>
                    </TableCell>
                    <TableCell className="text-xs">{parkName(doc.park)}</TableCell>
                    <TableCell className="text-xs">
                      <span className="inline-flex items-center gap-1">
                        {pageTypeLabel(doc.page_type)}
                        {doc.has_table && <TableIcon className="size-3.5 text-muted-foreground" aria-label="Contains tables" />}
                      </span>
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatCount(doc.active_chunks)}</TableCell>
                    <TableCell className="text-xs tabular-nums">{formatDate(doc.crawled_at)}</TableCell>
                  </TableRow>
                ))}
                {list && list.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                      No stored documents match these filters.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          {list && (
            <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
              <span className="tabular-nums">{formatCount(list.total)} documents</span>
              <Pager offset={offset} limit={PAGE_SIZE} total={list.total} onChange={setOffset} label="documents" />
            </div>
          )}
        </section>
      </div>
      <DocumentSheet docId={openDoc} onOpenChange={(open) => !open && setOpenDoc(null)} />
    </div>
  )
}
