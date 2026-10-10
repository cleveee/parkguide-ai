// Same-origin client for the loopback FastAPI bridge. The browser never talks
// to Azure or any other remote service; only /api/* on this origin.

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

export interface ChatTurn {
  turn_id: string
  selected_park: ParkCode
  question: string
  status: "answer" | "refusal" | "clarification"
  text: string
  claims: Claim[]
  sources: SourcePage[]
  history_content: string
  history_scope_reset: boolean
  runtime?: TurnRuntime
  reason: { code: string; category: ReasonCategory; detail: string } | null
  timing: { server_ms: number | null; answer_call_ms: number; pipeline_ms: number | null }
  history: { messages_received: number; messages_used: number; scope_reset: boolean }
  inspector: {
    retrieval: {
      ran: boolean
      query: string | null
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { credentials: "same-origin", ...init })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error
    throw new ApiError(0, "network_error", "The local ParkGuide server could not be reached. Is it still running?")
  }
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string; details?: ErrorDetails } } | null)?.error
    throw new ApiError(
      response.status,
      error?.code ?? "http_error",
      error?.message ?? `The server returned HTTP ${response.status}.`,
      error?.details ?? null,
    )
  }
  return body as T
}

export const getMeta = () => request<Meta>("/api/meta")

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

export const getPassages = (docId: string, offset = 0, limit = 20) =>
  request<PassageList>(`/api/documents/${encodeURIComponent(docId)}/passages?offset=${offset}&limit=${limit}`)

export interface HistoryMessage {
  role: "user" | "assistant"
  content: string
}

export const MAX_QUESTION_CHARS = 1000
export const MAX_HISTORY_MESSAGES = 12
export const MAX_HISTORY_CONTENT_CHARS = 4000

export const postChat = (body: { selected_park: ParkCode; question: string; history: HistoryMessage[] }, signal: AbortSignal) =>
  request<ChatTurn>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
