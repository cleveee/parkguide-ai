import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import type { Meta } from "@/lib/api"

const STEPS: { title: string; where: string; body: string }[] = [
  {
    title: "Your question and selected park first reach local checks",
    where: "This computer",
    body: "The browser sends them only to this loopback server. Pattern checks refuse recognized phrasings of other-park, live-condition and private-record requests before anything leaves the machine. They only recognize certain wordings: a differently worded request can continue to search and the steps below, where it may still be refused.",
  },
  {
    title: "The retrieval query is embedded when needed",
    where: "One Azure endpoint",
    body: "If the query vector is not already in the local cache, the retrieval query text is sent to the Azure embedding deployment. The vector is then saved in the local cache under the query's SHA-256 hash.",
  },
  {
    title: "Saved NPS passages are searched and reranked locally",
    where: "This computer",
    body: "SQLite, NumPy cosine similarity and BM25 search only the selected park's saved passages; a local cross-encoder reranks the candidates.",
  },
  {
    title: "An answer is drafted from selected snippets",
    where: "Same Azure resource (Luna)",
    body: "The question, the selected snippets and a bounded slice of this conversation are sent to Luna, which must cite passage IDs for every factual claim.",
  },
  {
    title: "Each claim gets an AI source review",
    where: "Same Azure resource (Luna)",
    body: "A separate review call receives the question, conversation, drafted claims and only the passages those claims cite. Unsupported claims are withheld; deterministic number, citation and quotation checks also run locally.",
  },
  {
    title: "Only reviewed claims and saved source links return",
    where: "This computer",
    body: "The browser receives the reviewed answer, saved excerpts and official NPS links. Nothing is displayed until review finishes.",
  },
]

// The hosted Vercel profile differs in where steps run and in skipping the reranker.
const HOSTED_STEPS: { title: string; where: string; body: string }[] = [
  {
    ...STEPS[0],
    where: "ParkGuide server function (Vercel)",
    body: "The browser sends them only to this site's server function. Pattern checks refuse recognized phrasings of other-park, live-condition and private-record requests before any Azure call. They only recognize certain wordings: a differently worded request can continue to search and the steps below, where it may still be refused.",
  },
  {
    ...STEPS[1],
    body: "If the query vector is not already in this server instance's temporary cache, the retrieval query text is sent to the Azure embedding deployment. The vector is then kept in that temporary cache under the query's SHA-256 hash.",
  },
  {
    title: "Saved NPS passages are searched on the server",
    where: "ParkGuide server function (Vercel)",
    body: "The bundled read-only SQLite index, NumPy cosine similarity and BM25 search only the selected park's saved passages, fused by reciprocal rank. The hosted version does not run the cross-encoder reranker that the local version uses.",
  },
  STEPS[3],
  STEPS[4],
  { ...STEPS[5], where: "ParkGuide server function (Vercel)" },
]

export function HowItWorks({ open, onOpenChange, meta }: { open: boolean; onOpenChange: (open: boolean) => void; meta: Meta | null }) {
  const hosted = meta?.runtime?.profile === "vercel"
  const steps = hosted ? HOSTED_STEPS : STEPS
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* A flex column with a bounded height and one min-h-0 overflow region: the
          body scrolls inside the dialog instead of spilling past the viewport. */}
      <DialogContent className="flex max-h-[min(85dvh,46rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-xl">
        <DialogHeader className="shrink-0 border-b p-4 pr-12">
          <DialogTitle>How ParkGuide answers</DialogTitle>
          <DialogDescription className="text-pretty">What happens to a question, what leaves this computer, and what stays on it.</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <div className="space-y-5 p-4 text-sm break-words">
            <p className="text-xs text-pretty text-muted-foreground">
              Each turn's inspector (Data flow tab) records what actually happened for that question. Use it rather than this general description.
            </p>
            <ol className="space-y-4">
              {steps.map((step, index) => (
                <li key={step.title} className="flex gap-3">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium tabular-nums text-muted-foreground">
                    {index + 1}
                  </span>
                  <div className="space-y-0.5">
                    <p className="font-medium text-pretty">{step.title}</p>
                    <p className="text-xs text-muted-foreground">{step.where}</p>
                    <p className="text-pretty text-foreground/80">{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>
            <div className="space-y-2 rounded-lg border bg-card p-3 text-xs text-pretty text-muted-foreground">
              <p>
                <span className="font-medium text-foreground">Snapshot, not live conditions.</span> Saved pages reflect their capture date. Closures, weather and
                availability can differ today.
              </p>
              <p>
                <span className="font-medium text-foreground">AI review is not human verification.</span> “Source review passed” means a model found verbatim
                supporting witnesses in the cited passages. It does not establish accuracy or guarantee the absence of errors.
              </p>
              {hosted ? (
                <p>
                  <span className="font-medium text-foreground">What stays where.</span> Conversation text is kept in this tab's memory and is lost on reload; it is
                  sent to the server function with each question, which does not store it. Each server instance keeps temporary derived data in{" "}
                  <code className="font-mono">/tmp</code> until it is recycled: the SHA-256 hash and vector of each embedded retrieval query (not its text), and a
                  budget ledger of each paid call's kind, time, status, tokens and estimated cost (no text).
                </p>
              ) : (
                <p>
                  <span className="font-medium text-foreground">What stays where.</span> Conversation text is kept in this tab's memory and is lost on reload; it is
                  sent to the local server with each question, which does not store it. Some derived data does persist on this computer: the local embedding cache
                  keeps the SHA-256 hash and vector of each embedded retrieval query (not its text), and the budget ledger records each paid call's kind, time,
                  status, tokens and estimated cost (no text).
                </p>
              )}
              {hosted && meta && (
                <>
                  <p>
                    <span className="font-medium text-foreground">Hosted retrieval differs from the evaluated setup.</span> {meta.runtime.rerank_reason}{" "}
                    {meta.runtime.evaluation_note}
                  </p>
                  <p>
                    <span className="font-medium text-foreground">Spending cap is per server instance.</span> {meta.runtime.budget.note}
                  </p>
                </>
              )}
              <p>
                <span className="font-medium text-foreground">Remote retention.</span> Text sent to Azure is handled under Azure's own terms. ParkGuide requests{" "}
                <code className="font-mono">store=false</code> for answer and review calls; that request does not by itself guarantee that the provider keeps no
                data.
              </p>
              {meta && (
                <>
                  <p>
                    <span className="font-medium text-foreground">The one Azure resource.</span>{" "}
                    <code className="font-mono break-all">{meta.models.azure_resource.endpoint}</code> serves both deployments:{" "}
                    <code className="font-mono">{meta.models.azure_resource.embedding_deployment}</code> for embeddings and{" "}
                    <code className="font-mono">{meta.models.azure_resource.generation_deployment}</code> (model {meta.models.generation.model}) for drafting and
                    review. No other model provider is called.
                  </p>
                  {hosted ? (
                    <p>
                      <span className="font-medium text-foreground">Models.</span> Embedding dimension {meta.models.embedding.dimension}. The reranker{" "}
                      {meta.models.reranker.model} is not used in this hosted version.
                    </p>
                  ) : (
                    <p>
                      <span className="font-medium text-foreground">Local models.</span> Embedding dimension {meta.models.embedding.dimension}. Reranker{" "}
                      {meta.models.reranker.model} runs on this computer from its local cache.
                    </p>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
