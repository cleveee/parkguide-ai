// Display helpers. A null value means "not captured", never zero.

export const NOT_CAPTURED = "Not captured"

export function formatMs(value: number | null | undefined) {
  if (value === null || value === undefined) return NOT_CAPTURED
  if (value < 1000) return `${Math.round(value)} ms`
  return `${(value / 1000).toFixed(value < 10_000 ? 2 : 1)} s`
}

export function formatCount(value: number | null | undefined) {
  if (value === null || value === undefined) return NOT_CAPTURED
  return value.toLocaleString("en-US")
}

export function formatUsd(value: number | null | undefined) {
  if (value === null || value === undefined) return NOT_CAPTURED
  if (value === 0) return "$0.00"
  // Never round a positive estimate (for example one embedding call) to zero:
  // keep three significant digits, switching to scientific notation if tiny.
  if (Math.abs(value) < 0.0001) return `$${value.toExponential(2)}`
  if (Math.abs(value) < 0.01) return `$${value.toPrecision(3)}`
  return `$${value.toFixed(4)}`
}

export function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined) return "—"
  const magnitude = Math.abs(value)
  return magnitude !== 0 && magnitude < 0.01 ? value.toExponential(2) : value.toFixed(magnitude < 1 ? 4 : 2)
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "Unknown"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
}

// Elapsed-time buckets, never calendar words like "today": a capture late on
// Oct 9 is "under 24 hours ago" on Oct 10, not "today".
export function captureAge(value: string | null | undefined, now = Date.now()) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  const hours = (now - date.getTime()) / 3_600_000
  if (hours < 0) return null
  if (hours < 24) return "captured under 24 hours ago"
  const days = Math.floor(hours / 24)
  if (days === 1) return "captured 1 day ago"
  if (days < 60) return `captured ${days} days ago`
  return `captured about ${Math.round(days / 30)} months ago`
}

/** Exact local timestamp with time zone, for tooltips and detail rows. */
export function formatDateTime(value: string | null | undefined) {
  if (!value) return "Unknown"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  })
}

export function pageTypeLabel(value: string | null | undefined) {
  return value === "pdf" ? "PDF" : value === "html" ? "HTML" : "Unknown type"
}
