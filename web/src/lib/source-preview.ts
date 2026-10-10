import type { SourcePage } from "./api"

export interface PreviewWitness { quote: string; claims: number[] }
export interface TextSegment { text: string; breakBefore?: boolean }
export interface Highlight { segment: number; start: number; end: number; witness: number }

export function pageWitnesses(page: SourcePage): PreviewWitness[] {
  const quotes = new Map<string, Set<number>>()
  for (const passage of page.passages) for (const witness of passage.reviewer_witnesses) {
    if (!witness.quote.trim()) continue
    const claims = quotes.get(witness.quote) ?? new Set<number>()
    claims.add(witness.claim_number)
    quotes.set(witness.quote, claims)
  }
  return Array.from(quotes, ([quote, claims]) => ({ quote, claims: [...claims].sort((a, b) => a - b) }))
}

/** Exact text matching with whitespace normalization and original character offsets.
 * Quotes may span inline tags; unrelated block boundaries still separate words.
 * No fuzzy match or invented substitute is presented as cited evidence.
 */
export function findWitnessMatches(segments: TextSegment[], quotes: string[]) {
  let text = ""
  const positions: ({ segment: number; offset: number } | null)[] = []
  const space = (position: { segment: number; offset: number } | null) => {
    if (!text.endsWith(" ")) { text += " "; positions.push(position) }
  }
  segments.forEach((segment, index) => {
    if (segment.breakBefore) space(null)
    for (let offset = 0; offset < segment.text.length; offset++) {
      const char = segment.text[offset]
      if (/\s/u.test(char)) space({ segment: index, offset })
      else { text += char; positions.push({ segment: index, offset }) }
    }
  })
  const highlights: Highlight[] = []
  const counts = quotes.map((quote, witness) => {
    const normalized = quote.trim().replace(/\s+/gu, " ")
    if (!normalized) return 0
    let count = 0
    let next = 0
    while (next <= text.length) {
      const start = text.indexOf(normalized, next)
      if (start === -1) break
      const ranges = new Map<number, { start: number; end: number }>()
      for (let index = start; index < start + normalized.length; index++) {
        const position = positions[index]
        if (!position) continue
        const range = ranges.get(position.segment)
        if (range) range.end = position.offset + 1
        else ranges.set(position.segment, { start: position.offset, end: position.offset + 1 })
      }
      for (const [segment, range] of ranges) highlights.push({ ...range, segment, witness })
      count++
      next = start + normalized.length
    }
    return count
  })
  return { highlights, counts }
}

const READER_STYLE = "html{color-scheme:light}body{margin:0;background:#fff;color:#202623;font:16px/1.7 system-ui,sans-serif}article{max-width:760px;margin:auto;padding:32px 28px 64px;overflow-wrap:anywhere}h1,h2,h3,h4,h5,h6{line-height:1.3;text-wrap:balance;margin:1.5em 0 .65em}h1{font-size:2rem}h2{font-size:1.4rem}h3{font-size:1.15rem}p{margin:.8em 0}li{margin:.35em 0}table{display:block;max-width:100%;overflow-x:auto;border-collapse:collapse;margin:1em 0}th,td{padding:8px 12px;border:1px solid #d4dcd7;text-align:left}th{background:#f0f5f2}pre{white-space:pre-wrap;font:inherit}mark{background:#d0f3e4;color:#123b2d;border-radius:3px;box-decoration-break:clone;padding:1px 0}mark[data-active=true]{background:#a9e5ca;outline:2px solid #008564;outline-offset:2px}blockquote{margin-left:0;border-left:3px solid #d4dcd7;padding-left:16px}@media(max-width:480px){article{padding:20px 16px 48px}h1{font-size:1.6rem}}"

const HIGHLIGHT_STYLE = 'mark[data-witness]{background:#d0f3e4!important;color:#123b2d!important;border-radius:3px;box-decoration-break:clone;padding:1px 0}mark[data-witness][data-active=true]{background:#a9e5ca!important;outline:2px solid #008564;outline-offset:2px}'

export function highlightedPreview(markup: string, witnesses: PreviewWitness[], layout: "reader" | "website" = "reader") {
  const document = new DOMParser().parseFromString(markup, "text/html")
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const nodes: Text[] = []
  const segments: TextSegment[] = []
  let previousBlock: Element | null = null
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node as Text
    if (text.parentElement?.closest("style,script,noscript,template,textarea")) continue
    const block = text.parentElement?.closest("p,li,h1,h2,h3,h4,h5,h6,td,th,pre,blockquote,dt,dd,div,section") ?? null
    nodes.push(text)
    segments.push({ text: text.data, breakBefore: nodes.length > 1 && block !== previousBlock })
    previousBlock = block
  }
  const result = findWitnessMatches(segments, witnesses.map((witness) => witness.quote))
  nodes.forEach((node, segment) => {
    const ranges = result.highlights.filter((range) => range.segment === segment)
    if (!ranges.length) return
    const points = [...new Set([0, node.length, ...ranges.flatMap((range) => [range.start, range.end])])].sort((a, b) => a - b)
    const fragment = document.createDocumentFragment()
    for (let index = 0; index < points.length - 1; index++) {
      const start = points[index], end = points[index + 1]
      const active = ranges.filter((range) => range.start <= start && range.end >= end)
      const part = document.createTextNode(node.data.slice(start, end))
      if (active.length) {
        const mark = document.createElement("mark")
        mark.setAttribute("data-witness", [...new Set(active.map((range) => range.witness))].join(" "))
        mark.append(part)
        fragment.append(mark)
      } else fragment.append(part)
    }
    node.replaceWith(fragment)
  })
  if (layout === "website") {
    const style = document.createElement("style")
    style.textContent = HIGHLIGHT_STYLE
    document.head.append(style)
    return { counts: result.counts, html: '<!doctype html>' + document.documentElement.outerHTML }
  }
  return { counts: result.counts, html: '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>' + READER_STYLE + '</style></head><body><article>' + document.body.innerHTML + '</article></body></html>' }
}
