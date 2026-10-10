"""Generate coursework draft reports from saved real artifacts."""
import json
from pathlib import Path

from .budget import Budget
from .runtime import ROOT, config, read_jsonl


def _json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def generate_reports():
    destination = ROOT / "reports"
    destination.mkdir(exist_ok=True)
    corpus = _json(ROOT / "data/corpus_summary.json", {})
    fixed = _json(ROOT / "artifacts/builds/fixed.json", {})
    structure = _json(ROOT / "artifacts/builds/structure.json", {})
    gold_path = ROOT / "data/evaluation/gold-drafts.jsonl"
    gold = read_jsonl(gold_path) if gold_path.exists() else []
    pointer = _json(ROOT / "artifacts/latest-diagnostic.json", {})
    run_folder = Path(pointer["run"]) if pointer.get("run") else None
    results = read_jsonl(run_folder / "results.jsonl") if run_folder and (run_folder / "results.jsonl").exists() else []
    summaries = _json(run_folder / "summary.json", {}) if run_folder else {}
    controlled_pointer = _json(ROOT / 'artifacts/latest-controlled.json',{})
    controlled_folder=Path(controlled_pointer['run']) if controlled_pointer.get('run') else None
    controlled_summaries=_json(controlled_folder/'summary.json',{}) if controlled_folder else {}
    initial_review_path=ROOT/'artifacts/reviews/initial-semantic-review.jsonl'
    initial_review=read_jsonl(initial_review_path) if initial_review_path.exists() else []
    latest_review_path=ROOT/'artifacts/reviews/latest-semantic-review.jsonl'
    latest_review=read_jsonl(latest_review_path) if latest_review_path.exists() else []
    review_counts={}
    for row in latest_review:
        group=row.get('variant') or 'dialogues'
        label=str(row.get('semantic_correct'))
        review_counts.setdefault(group,{})[label]=review_counts.setdefault(group,{}).get(label,0)+1
    dialogue_pointer = _json(ROOT / "artifacts/latest-dialogues.json", {})
    migration = _json(ROOT / "artifacts/migration/proof.json", {})
    if migration.get('previous_chunk_ids'):
        migration['previous_chunk_count']=len(migration.pop('previous_chunk_ids'))
    common = "These are implementation reports. Gold verification, semantic grading, and the final held-out benchmark remain subject to real human review. Diagnostic scores are not assignment-valid gold accuracy.\n"
    files = {}
    files["00_proposal.md"] = f"# ParkGuide proposal and implementation scope\n\nLocal Python/SQLite/NumPy/BM25/Streamlit application using one existing Azure resource for {config()['embedding']['deployment']} embeddings and {config()['generation']['model']} generation/claim review. No remote, commits, pushes, or deployment.\n\nSee docs/PLAN.md for architecture, sources, IDs, constraints, and approved scope. Robin confirmed instructor topic approval; the crawler contact is an explicit example.com placeholder at Robin's request. That contact does not satisfy the course's real-email requirement.\n"
    files["01_ingestion.md"] = "# Ingestion evidence\n\n" + common + "\nCaptured corpus summary:\n\n```json\n" + json.dumps(corpus, indent=2) + "\n```\n\nRaw bytes precede parsing and have URL/UTC/SHA provenance in data/raw/manifest.jsonl. Layout-table and merged-header fixes reprocessed saved bytes. Rotated PDF chart headers and pattern-based contact redaction remain documented limitations.\n"
    stats = {name: build.get("statistics") for name, build in (("fixed", fixed), ("structure", structure))}
    files["02_chunking.md"] = "# Chunking and offline migration\n\n" + common + "\nBoth strategies count complete inputs, retain source spans, and enforce a 200-token limit. Fixed overlap is 40 tokens; structure-aware chunks retain headings/table headers.\n\n```json\n" + json.dumps({"statistics": stats, "migration": migration}, indent=2) + "\n```\n\nMigration proof is performed on a database copy so baseline experiments remain reproducible. See docs/RETRIEVAL.md.\n"
    verified = sum(row.get("verification_status") == "human_verified" for row in gold)
    quotas = {category: sum(row["category"] == category for row in gold) for category in sorted({row["category"] for row in gold})}
    files["03_golden_set.md"] = f"# Golden-set review state\n\n{common}\nAuthored source-based drafts: {len(gold)}. Human-verified records: {verified}.\n\nCategory counts:\n\n```json\n{json.dumps(quotas, indent=2)}\n```\n\nQuestions were authored before live chatbot outputs. See data/evaluation/GOLD_REVIEW.md and gold-drafts.jsonl for evidence spans and proposed answers. Agents cannot mark human review complete. The 24/16 split and sealed final test are created only after actual verification. Twelve separate diagnostic questions and six conversations supplement the gold set.\n"
    table = "| Variant | Items | Errors | Evidence@5 | Evidence@20 | MRR | nDCG@10 |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n"
    for name, summary in controlled_summaries.items():
        def number(metric):
            value = summary.get(metric, {}).get("mean")
            return "N/A" if value is None else f"{value:.3f}"
        table += f"| {name} | {summary['items']} | {summary['errors']} | {number('evidence_coverage_5')} | {number('evidence_coverage_20')} | {number('mrr')} | {number('ndcg_10')} |\n"
    files["04_retrieval_reranking.md"] = "# Retrieval and reranking development evidence\n\n" + common + "\n" + table + "\nStandard chunk Recall@5/@20 and other denominators are retained in the saved summary JSON. Evidence coverage uses immutable source spans; chunk qrels are rebuilt per strategy. Compare fixed dense → structure dense → hybrid → reranker one factor at a time. These are non-gold diagnostics. Reranker scores are relevance scores, not confidence probabilities. The pre-rerank pool is limited to 20; post-rerank context is at most five.\n\nControlled run: " + str(controlled_folder or "not executed") + "\n\nIn that historical run B3 labels the reranking ablation. Current final B3 uses structure-aware hybrid with reranking disabled by default; the local reranker remains integrated and selectable. See docs/DIAGNOSTIC_ANALYSIS.md and docs/CANDIDATE_ANALYSIS.md for paired intervals, ceiling, and measured added latency. No positive reranker lift was established.\n"
    files["05_generation.md"] = "# Generation and actual conversations\n\n" + common + "\nThe provider uses structured claim objects, allowed source IDs, temperature zero, and an explicit source-only prompt. B0 has a documented closed-book exception. Response rendering uses trusted URLs. Guards block unknown IDs, unsupported numerical witnesses, generated URLs, and more than 25 consecutive copied words per source page. These guards do not prove semantic support; separate review is required.\n\nActual conversation run:\n\n```json\n" + json.dumps(dialogue_pointer, indent=2) + "\n```\n\nHistory uses actual previous assistant responses and fresh factual retrieval. Search traces include filters and pre/post scores. Source dates are snapshot metadata, not proof of current safety.\n"
    failures = [row for row in results if "error" in row or not row.get("grade", {}).get("diagnostic_pass", False)]
    review_rows = [{"item_id": row["item_id"], "configuration": row["configuration"], "run": str(run_folder), "observed_guard_errors": row.get("result", {}).get("guard_errors"), "provider_error": row.get("error"), "proposed_failure_class": None, "human_label": None, "reviewer": None} for row in failures]
    # Source-backed AI failure proposals are separate from noisy lexical misses.
    semantic_failures=[row for row in initial_review if row.get('observed_failure')]
    if semantic_failures:
        review_rows=[{**row,'human_label':None,'human_reviewer':None} for row in semantic_failures]
    (destination / "failure-review.jsonl").write_text("".join(json.dumps(row) + "\n" for row in review_rows))
    files["06_final_performance.md"] = "# Performance and remaining final-test work\n\n" + common + "\nThe sealed final test has not been consumed. No final gold accuracy, human-calibrated semantic citation score, or established course improvement is claimed. Current candidate diagnostic summaries:\n\n```json\n" + json.dumps(summaries, indent=2) + "\n```\n\nAI provisional semantic review counts (the linked review retains exact input hashes; not human labels):\n\n```json\n" + json.dumps(review_counts,indent=2) + "\n```\n\nAPI ledger:\n\n```json\n" + json.dumps(Budget().summary(), indent=2) + f"\n```\n\nThere are {len(review_rows)} actual observed failure instances proposed in failure-review.jsonl, each with an immutable run/item and source evidence when available. Their hand labels require human confirmation; lexical misses are not automatically semantic failures. Actual token-based costs are dated list-price estimates. Run cost fields include successful generation/review only; query embedding and failed-call reservations are included in the whole-implementation ledger rather than attributed per query. Formal B0-incorrect subset reporting awaits human labels. Pairwise intervals from diagnostic observations are separate from final gold inference. See docs/ITERATIONS.md, docs/LATEST_REVIEW.md, and docs/STATUS.md for candidate selection, AI provisional judgments, and remaining failures.\n"
    files["07_ethics.md"] = "# Ethics, reliability, and AI-use evidence\n\n" + common + "\nCoded safeguards: retrieved text is explicitly untrusted; generation is source-only; citation/number/quote checks can withhold output; current park safety cannot be inferred from dated text; high-stakes questions receive limitations and referral. UI states the saved-snapshot limit. Robots/allowlists/rate control and directory exclusions constrain crawling. Pattern-based contact redaction and PDF/table extraction need review.\n\nAI assistance: Codex and scoped subagents implemented ingestion, chunking/storage/retrieval, generation, evaluation, and reports. Candidate questions and diagnostic grades are AI proposals. No agent impersonates a human verifier. Every metric must be explained from formulas and saved outputs. GitHub protection/team PRs, individual contributions, and a classroom demonstration remain deferred course requirements.\n"
    files['05_generation.md']+='\nAn optional independent AI claim reviewer checks each assertion against its cited passages and withholds unsupported claims. It uses the same approved model with a separate prompt and budgeted request. This improves inspection but does not prove entailment; human calibration remains required. Saved traces include all original claims and reviewer decisions. See docs/CLAIM_REVIEW.md.\n'
    files['05_generation.md']+='\nExplicit table requests filter to captured table-bearing pages. Named-row context packing retains the source row within the candidate pool without altering recorded rankings. Difference questions can use a deterministic Decimal calculation from named rows, explicit header units, and immutable source cells; derived values have an equation/operand trace and pass the same citation/review guards. The original model output is preserved. Per-turn histories are now snapshots; earlier immutable dialogue artifacts have a documented mutable-trace alias limitation.\n'
    files['07_ethics.md']+='\nPaid synthetic retrieved-injection and expired-source diagnostics are retained in artifacts/latest-safeguards.json. These fixtures are not NPS corpus records or formal benchmark items.\n'
    for name, text in files.items():
        (destination / name).write_text(text)
    return {"reports": list(files), "diagnostic_run": str(run_folder) if run_folder else None, "human_verified_gold": verified, "final_test_consumed": (ROOT / "artifacts/final-test/results.jsonl").exists()}
