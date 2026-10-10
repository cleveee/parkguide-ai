// Same-origin client for the loopback FastAPI bridge. The browser never talks
// to Azure; application data requests use /api/* on this origin. Source previews
// load the official website's stylesheets, fonts and images separately.

export type ParkCode = "yose" | "yell" | "grca"

export const PARKS: { code: ParkCode; name: string }[] = [
  { code: "yose", name: "Yosemite" },
  { code: "yell", name: "Yellowstone" },
  { code: "grca", name: "Grand Canyon" },
]

export const parkName = (code: string | null | undefined) =>
  PARKS.find((park) => park.code === code)?.name ?? "Unknown park"

export interface ParkMeta {
  code: ParkCode
  name: string
  documents: number
  html: number
  pdf: number
  table_documents: number
  active_chunks: number
  captured_earliest: string | null
  captured_latest: string | null
}

export interface BuildMeta {
  build_id: string
  active: boolean
  strategy: string | null
  created_at: string | null
  chunk_count: number
  vector_count: number
  dimension: number | null
  embedding_deployment: string | null
  target_tokens: number | null
  overlap_tokens: number | null
}

export interface Meta {
  parks: ParkMeta[]
  totals: {
    documents: number
    html: number
    pdf: number
    table_documents: number
    chunks_all_builds: number
    vectors_all_builds: number
  }
  active_build: BuildMeta | null
  builds: BuildMeta[]
  models: {
    embedding: { deployment: string; dimension: number }
    generation: { model: string; deployment: string }
    reranker: { model: string; revision: string; enabled: boolean }
    azure_resource: { endpoint: string; embedding_deployment: string; generation_deployment: string; generation_store_requested: boolean }
  }
  local_persistence: { conversation_text: string; embedding_cache: string; budget_ledger: string }
  runtime: RuntimeProfile
  retrieval: {
    mode: string
    strategy: string
    candidate_count: number
    final_context_count: number
    rrf_k: number
    selected_park_rerank: boolean
    context_token_budget: number
  }
  chat: { ready: boolean; reason: string | null }
  history_storage: string
  generated_at: string
}

/** Effective serving profile: "local" (loopback, reranker on) or "vercel" (hosted, reranker off). */
export interface RuntimeProfile {
  profile: "local" | "vercel"
  rerank_enabled: boolean
  rerank_reason: string
  evaluation_note: string
  budget: { cap_usd: number; scope: "per_instance" | "local_shared_ledger"; note: string }
  state_storage: string
  request_serialization: string
}

export interface TurnRuntime {
  profile: "local" | "vercel"
  rerank_enabled: boolean
  rerank_reason: string
  evaluation_note: string
  budget_scope: "per_instance" | "local_shared_ledger"
}

export interface Span {
  start: number
  end: number
  kind: string
}

export interface SourcePassage {
  chunk_id: string
  doc_id: string
  heading_path: string
  excerpt: string
  excerpt_leading_omission: boolean
  excerpt_truncated: boolean
  saved_text: string
  pdf_start_page: number | null
  passage_url: string
  source_spans: Span[]
  claim_numbers: number[]
  reviewer_witnesses: { claim_number: number; quote: string }[]
}

export interface SourcePage {
  number: number
  title: string
  source_url: string
  park: ParkCode
  page_type: "html" | "pdf" | string
  effective_date: string | null
  crawled_at: string | null
  captured_label: string
  passages: SourcePassage[]
}

export interface Claim {
  number: number
  text: string
  source_numbers: number[]
  review: { reason: string | null } | null
}

export type Scores = { dense: number | null; bm25: number | null; rrf: number | null; rerank: number | null }

export interface Candidate {
  chunk_id: string
  doc_id: string
  title: string | null
  heading_path: string | null
  source_url: string | null
  page_type: string | null
  park: ParkCode | null
  in_selected_park: boolean
  pre_rank: number | null
  post_rank: number | null
  scores: Scores
  retriever_ranks: { dense?: number | null; bm25?: number | null }
  in_context: boolean
  cited: boolean
  snippet: string
}

export interface SuggestedQuestion {
  id: string
  question: string
  source_url: string
  supporting_quote: string
  evidence_ids: string[]
}

export interface ChatTurn {
  turn_id: string
  selected_park: ParkCode
  question: string
  status: "answer" | "refusal" | "clarification"
  text: string
  claims: Claim[]
  sources: SourcePage[]
  history_content: string
  suggested_questions?: SuggestedQuestion[]
  history_evidence_ids?: string[]
  history_scope_reset: boolean
  runtime?: TurnRuntime
  reason: { code: string; category: ReasonCategory; detail: string } | null
  timing: { server_ms: number | null; answer_call_ms: number; pipeline_ms: number | null }
  history: { messages_received: number; messages_used: number; scope_reset: boolean }
  inspector: {
    retrieval: {
      ran: boolean
      query: string | null
      keyword_query?: string | null
      keyword_current_terms?: string[] | null
      keyword_candidate_count?: number | null
      filters: { parks: string[]; source_url_count: number }
      mode: string | null
      build_id: string | null
      build_strategy: string
      rerank_enabled: boolean
      eligible_count: number | null
      candidate_count: number | null
      requested_candidates: number | null
      final_count: number
      context_count: number
      shortfall: boolean | null
      timings_ms: { load_ms: number | null; retrieval_ms: number | null; rerank_ms: number | null; total_ms: number | null }
      score_labels: Record<keyof Scores, string>
      candidates: Candidate[]
      context_ids: string[]
      context_selection: { method: string; selected_ids: string[] } | null
    }
    embedding: EmbeddingObservation
    generation: {
      ran: boolean
      returned_model: string | null
      requested_deployment: string | null
      input_tokens: number | null
      output_tokens: number | null
      elapsed_ms: number | null
      cost_estimate_usd: number | null
    }
    review: {
      status: "passed" | "not_run" | "error" | "partially_withheld" | "all_withheld"
      model?: string | null
      input_tokens?: number | null
      output_tokens?: number | null
      elapsed_ms?: number | null
      cost_estimate_usd?: number | null
      withheld_claims?: number | null
      error_type?: string | null
      error_message?: string | null
      validation_reason?: string | null
    }
    ledger_window: LedgerWindow
    guard_errors: string[]
    integrity_errors: string[]
    derivation: Derivation | null
    config_hash: string | null
    timestamp: string | null
  }
}

export type ReasonCategory =
  | "local_preflight"
  | "scope_check"
  | "validation_failure"
  | "review_failure"
  | "review_rejected"
  | "no_evidence"
  | "model_refusal"
  | "model_clarification"

export interface EmbeddingObservation {
  status: "not_requested" | "not_captured" | "azure_request_recorded" | "azure_attempt_failed_recorded" | "no_azure_request_recorded"
  elapsed_ms: number | null
  query_sha256: string | null
  cache_file_present_before_call: boolean | null
  deployment: string
}

export interface LedgerKind {
  events: number
  reported_usage: number
  failed_attempts: number
  unsettled_reservations: number
  input_tokens: number | null
  output_tokens: number | null
  events_without_token_usage: number
  cost_estimate_usd: number
}

export type LedgerWindow =
  | { captured: false; reason: string }
  | {
      captured: true
      events: number
      cost_estimate_usd: number
      by_kind: Partial<Record<"embedding" | "generation" | "other", LedgerKind>>
      includes_reserved_maximums: boolean
      basis: string
      limitation: string
    }

export interface Derivation {
  operation: string | null
  column: string | null
  unit: string | null
  result: string | null
  equation: string | null
  operands: { row_label: string | null; source_cell: string | null; value: string | null; chunk_id: string; source_spans: Span[] }[]
  note: string
}

export interface ErrorDetails {
  ledger_window?: LedgerWindow
  embedding?: EmbeddingObservation
  answer_call_ms?: number
}

export interface DocumentSummary {
  doc_id: string
  title: string
  source_url: string | null
  park: ParkCode | null
  page_type: string
  has_table: boolean
  effective_date: string | null
  crawled_at: string | null
  captured_label: string
  active_chunks: number
}

export interface DocumentList {
  total: number
  offset: number
  limit: number
  items: DocumentSummary[]
}

export interface DocumentDetail extends Omit<DocumentSummary, "active_chunks"> {
  content_hash: string
  block_count: number
  block_offset: number
  block_limit: number
  sections: { index: number; heading_path: string; kind: string; start: number | null; end: number | null; text: string; truncated: boolean }[]
  chunks_by_build: { build_id: string; strategy: string | null; active: boolean; chunks: number }[]
}

export interface PassageList {
  build_id: string
  total: number
  offset: number
  limit: number
  passages: { position: number; chunk_id: string; heading_path: string; text: string; token_count: number; source_spans: Span[] }[]
}

export class ApiError extends Error {
  status: number
  code: string
  details: ErrorDetails | null

  constructor(status: number, code: string, message: string, details: ErrorDetails | null = null) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 20_000): Promise<T> {
  const controller = new AbortController()
  const cancel = () => controller.abort(init?.signal?.reason)
  if (init?.signal?.aborted) cancel()
  else init?.signal?.addEventListener("abort", cancel, { once: true })
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  try {
    const response = await fetch(path, { credentials: "same-origin", ...init, signal: controller.signal })
    let body: unknown = null
    try {
      body = await response.json()
    } catch (error) {
      if (controller.signal.aborted) throw error
    }
    if (!response.ok) {
      const error = (body as { error?: { code?: string; message?: string; details?: ErrorDetails } } | null)?.error
      throw new ApiError(
        response.status,
        error?.code ?? "http_error",
        error?.message ?? (response.status >= 500 ? "ParkGuide is temporarily unavailable. Please try again shortly." : `The server returned HTTP ${response.status}.`),
        error?.details ?? null,
      )
    }
    if (!body || typeof body !== "object" || Array.isArray(body)) {
      throw new ApiError(response.status, "invalid_response", "ParkGuide returned an unreadable response. Please try again.")
    }
    return body as T
  } catch (error) {
    if (timedOut) throw new ApiError(0, "request_timeout", "The request took too long. The server may still be finishing it; wait a moment before retrying.")
    if (error instanceof DOMException && error.name === "AbortError") throw error
    if (error instanceof ApiError) throw error
    throw new ApiError(0, "network_error", "ParkGuide could not be reached. Check your connection and try again.")
  } finally {
    clearTimeout(timer)
    init?.signal?.removeEventListener("abort", cancel)
  }
}

const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === "object" && !Array.isArray(value)
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every((item) => typeof item === "string")
const numbers = (value: unknown): value is number[] => Array.isArray(value) && value.every((item) => typeof item === "number" && Number.isFinite(item))
const objects = (value: unknown, check: (item: Record<string, unknown>) => boolean): boolean => Array.isArray(value) && value.every((item) => object(item) && check(item))
const invalidResponse = () => new ApiError(200, "invalid_response", "ParkGuide returned an incomplete response. Please try again.")

// Guard the structures rendered by the app before a successful HTTP response
// enters React state. Source support and citation integrity remain server checks.
function validSuggestions(value: unknown, park: unknown): boolean {
  if (value === undefined) return true
  if (!Array.isArray(value) || value.length > 3) return false
  const questions = new Set<string>()
  const ids = new Set<string>()
  return value.every((item) => {
    if (!object(item) || typeof item.id !== "string" || !/^[A-Za-z0-9_-]{1,80}$/.test(item.id) || ids.has(item.id) || typeof item.question !== "string" || !item.question.trim() || item.question.length > 1000
      || typeof item.supporting_quote !== "string" || !item.supporting_quote.trim() || item.supporting_quote.length > 2000
      || !strings(item.evidence_ids) || item.evidence_ids.length < 1 || item.evidence_ids.length > 5
      || item.evidence_ids.some((id) => !/^[A-Za-z0-9_-]{1,128}$/.test(id)) || typeof item.source_url !== "string") return false
    try {
      const url = new URL(item.source_url)
      if (url.protocol !== "https:" || url.host !== "www.nps.gov" || url.username || url.password
        || !url.pathname.startsWith(`/${park}/planyourvisit/`)) return false
    } catch { return false }
    const key = item.question.trim().toLowerCase()
    if (questions.has(key)) return false
    questions.add(key)
    ids.add(item.id)
    return true
  })
}

export function validChatTurn(value: unknown): value is ChatTurn {
  if (!object(value) || !PARKS.some((park) => park.code === value.selected_park)
      || !["answer", "refusal", "clarification"].includes(String(value.status))
      || typeof value.text !== "string" || typeof value.history_content !== "string"
      || (value.history_evidence_ids !== undefined && (!strings(value.history_evidence_ids) || value.history_evidence_ids.length > 5))
      || typeof value.turn_id !== "string" || typeof value.question !== "string"
      || !object(value.history) || !object(value.timing)
      || !(value.reason === null || (object(value.reason) && typeof value.reason.code === "string" && typeof value.reason.category === "string" && typeof value.reason.detail === "string"))
      || !objects(value.claims, (claim) => typeof claim.number === "number" && typeof claim.text === "string" && numbers(claim.source_numbers))
      || !objects(value.sources, (page) => typeof page.number === "number" && typeof page.title === "string" && typeof page.source_url === "string"
        && objects(page.passages, (passage) => typeof passage.chunk_id === "string" && typeof passage.saved_text === "string" && typeof passage.excerpt === "string"
          && numbers(passage.claim_numbers) && objects(passage.source_spans, (span) => typeof span.start === "number" && typeof span.end === "number")
          && objects(passage.reviewer_witnesses, (witness) => typeof witness.claim_number === "number" && typeof witness.quote === "string")))
      || !validSuggestions(value.suggested_questions, value.selected_park)
      || (value.status !== "answer" && Array.isArray(value.suggested_questions) && value.suggested_questions.length > 0)
      || !object(value.inspector)) return false
  const detail = value.inspector
  if (!object(detail.retrieval) || !object(detail.embedding) || !object(detail.generation) || !object(detail.review)
      || !object(detail.ledger_window) || typeof detail.ledger_window.captured !== "boolean"
      || !strings(detail.guard_errors) || !strings(detail.integrity_errors)) return false
  const retrieval = detail.retrieval
  return object(retrieval.filters) && strings(retrieval.filters.parks) && object(retrieval.timings_ms)
    && (retrieval.keyword_current_terms == null || strings(retrieval.keyword_current_terms))
    && object(retrieval.score_labels) && strings(retrieval.context_ids)
    && objects(retrieval.candidates, (item) => typeof item.chunk_id === "string" && typeof item.snippet === "string" && object(item.scores) && object(item.retriever_ranks))
    && (!detail.ledger_window.captured || (object(detail.ledger_window.by_kind) && Object.values(detail.ledger_window.by_kind).every(object)))
}

export const getMeta = async () => {
  const value = await request<unknown>("/api/meta")
  if (!object(value) || !objects(value.parks, (park) => typeof park.code === "string" && typeof park.name === "string")
      || !object(value.chat) || typeof value.chat.ready !== "boolean" || !object(value.totals)
      || !Array.isArray(value.builds) || !object(value.models) || !object(value.models.embedding)
      || !object(value.models.generation) || !object(value.models.reranker) || !object(value.models.azure_resource)
      || !object(value.runtime) || !object(value.runtime.budget) || !object(value.retrieval) || !object(value.local_persistence)) throw invalidResponse()
  return value as unknown as Meta
}

export function listDocuments(params: { park?: ParkCode; q?: string; page_type?: string; has_table?: boolean; offset: number; limit: number }, signal?: AbortSignal) {
  const query = new URLSearchParams()
  if (params.park) query.set("park", params.park)
  if (params.q) query.set("q", params.q)
  if (params.page_type) query.set("page_type", params.page_type)
  if (params.has_table !== undefined) query.set("has_table", String(params.has_table))
  query.set("offset", String(params.offset))
  query.set("limit", String(params.limit))
  return request<DocumentList>(`/api/documents?${query}`, { signal })
}

export const getDocument = (docId: string, blockOffset = 0, blockLimit = 40) =>
  request<DocumentDetail>(`/api/documents/${encodeURIComponent(docId)}?block_offset=${blockOffset}&block_limit=${blockLimit}`)

export interface SourcePreview {
  doc_id: string
  source_url: string
  title: string
  page_type: string
  crawled_at: string | null
  mode: "html_reader" | "html_page" | "pdf_text"
  html: string
  loaded_at?: string
  content_origin?: "live"
}

export async function getSourcePreview(docId: string, signal: AbortSignal, view: "reader" | "website" = "reader"): Promise<SourcePreview> {
  const value = await request<SourcePreview>(`/api/documents/${encodeURIComponent(docId)}/preview${view === "website" ? "?view=website" : ""}`, { signal })
  if (value.doc_id !== docId || typeof value.html !== "string" || typeof value.source_url !== "string"
      || typeof value.title !== "string" || !["html_reader", "html_page", "pdf_text"].includes(value.mode)) throw invalidResponse()
  return value
}

export const getPassages = (docId: string, offset = 0, limit = 20) =>
  request<PassageList>(`/api/documents/${encodeURIComponent(docId)}/passages?offset=${offset}&limit=${limit}`)

export interface HistoryMessage {
  role: "user" | "assistant"
  content: string
  evidence_ids?: string[]
}

export const MAX_QUESTION_CHARS = 1000
export const MAX_HISTORY_MESSAGES = 12
export const MAX_HISTORY_CONTENT_CHARS = 4000

export const postChat = async (body: { selected_park: ParkCode; question: string; history: HistoryMessage[] }, signal: AbortSignal) => {
  const value = await request<unknown>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  }, 110_000)
  if (!validChatTurn(value)) throw invalidResponse()
  return value
}
