"""Build an offline, secret-free snapshot from existing local run artifacts. No API calls."""
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import base64
import hashlib
import json
from collections import Counter
from parkguide.source_links import cited_source_pages

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard"
sources = {}


def read(path, lines=False, text=False):
    p = ROOT / path
    raw = p.read_bytes()
    sources[path] = {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    value = raw.decode()
    if text:
        return value
    return [json.loads(row) for row in value.splitlines() if row.strip()] if lines else json.loads(value)


def call_metadata(call):
    """Report only recorded public call metadata, never infer a provider/model."""
    return {k: call.get(k) for k in (
        "provider", "requested_model", "model", "usage", "elapsed_ms",
        "prompt_sha256", "cost_estimate_usd", "error", "validation_reason",
        "diagnostics", "withheld_claims", "decisions",
    ) if k in call}


def build():
    stages = read("artifacts/dashboard/stage-audit.json")
    technical = read("artifacts/dashboard/technical-audit.json")
    corpus = read("data/corpus_summary.json")
    docs = read("data/documents.jsonl", lines=True)
    documents = [{k: d.get(k) for k in ("doc_id", "title", "source_url", "page_type", "effective_date", "crawled_at", "has_table", "raw_sha256", "content_hash")} | {"characters": len(d["normalized_text"]), "blocks": len(d["blocks"]), "park": d["source_url"].split("/")[3]} for d in docs]
    builds = []
    for strategy in ("fixed", "structure"):
        b = read(f"artifacts/builds/{strategy}.json")
        builds.append({k: b.get(k) for k in ("build_id", "strategy", "created_at", "dimension", "vector_sha256", "ordered_chunk_ids_sha256", "statistics", "migration", "integrity")} | {"chunking": b["identity"].get("chunking", b["identity"].get("chunker"))})
    reviews = read("artifacts/reviews/latest-semantic-review.jsonl", lines=True)
    review_counts = {}
    for key in ("B0", "B1", "B2", "B3", "dialogues"):
        selected = [r for r in reviews if (r["kind"] == "dialogue" if key == "dialogues" else r["kind"] == "diagnostic" and r["variant"] == key)]
        counts = Counter("correct" if r["semantic_correct"] is True else "incorrect" if r["semantic_correct"] is False else "uncertain" for r in selected)
        claims = Counter()
        for r in selected:
            claims.update(r["claim_counts"])
        review_counts[key] = {"total": len(selected), **dict(counts), "claims": dict(claims)}
    review_details = [{k: r.get(k) for k in ("kind", "run_id", "variant", "item_id", "dialogue_id", "turn", "question", "semantic_correct", "claim_counts", "rootcause", "failure_class", "warnings", "human_review_pending", "human_verifier")} for r in reviews]
    evidence = {}
    for p in sorted((ROOT / "docs").glob("*.md")) + sorted((ROOT / "reports").glob("*.md")) + [ROOT / "README.md"]:
        rel = str(p.relative_to(ROOT))
        evidence[rel] = read(rel, text=True)
    # Derive display attribution from the unchanged raw results, not Markdown
    # URLs or AI review proposals. Preserve the original stage audit on disk.
    attribution = Counter()
    for s in stages["stages"]:
        curated = {
            (row.get("dialogue_id"), row.get("turn")) if row.get("dialogue_id")
            else (row.get("configuration"), row.get("item_id")): row
            for row in s["curated_rows"]
        }
        for run in (s.get("single_turn"), s.get("dialogues")):
            if run and run.get("path"):
                for row in read(run["path"], lines=True):
                    key = (row.get("dialogue_id"), row.get("turn")) if row.get("dialogue_id") else (row.get("configuration"), row.get("item_id"))
                    display = curated[key]
                    trace = row.get("result", {})
                    pages = cited_source_pages(trace)
                    claims = trace.get("response", {}).get("claims", [])
                    display["answer_text"] = "\n\n".join(claim["text"] for claim in claims) if claims else display.get("rendered")
                    # Keep the bounded excerpt and immutable IDs/spans here;
                    # complete text is preserved in the unchanged raw artifact.
                    for page in pages:
                        for passage in page["passages"]:
                            passage.pop("text", None)
                    display["sources_used"] = pages
                    attribution["attempts"] += 1
                    attribution["responses_with_sources"] += bool(pages)
                    attribution["source_page_cards"] += len(pages)
                    attribution["cited_passages"] += sum(len(page["passages"]) for page in pages)
                read(str(Path(run["path"]).with_name("manifest.json")))
    for path in (
        "data/raw/manifest.jsonl",
        "artifacts/reviews/initial-semantic-review.jsonl",
        "artifacts/reviews/pre-runtime-semantic-review.jsonl",
        "artifacts/safeguards/b1b7b32f87bb4bc18194efcba4b3cf1f/results.jsonl",
        "artifacts/safeguards/e216f1e3fe814f20814768ebf7504c49/results.jsonl",
    ):
        read(path, lines=True)
    setup_evidence, retrieval_evidence = {}, {}
    for folder, values in (("artifacts/setup", setup_evidence), ("artifacts/retrieval", retrieval_evidence)):
        for p in sorted((ROOT / folder).glob("*.json")):
            rel = str(p.relative_to(ROOT))
            values[rel] = read(rel)
    read("artifacts/migration/proof.json")
    read("data/evaluation/gold-draft-manifest.json")
    failures = read("reports/failure-review.jsonl", lines=True)
    analysis_paths = {
        "initial": "artifacts/runs/20261010T035053Z-24ef6136/analysis-5c0b68825595/analysis.json",
        "reranking": "artifacts/runs/20261010T040558Z-c2f6c2da/candidate-analysis-fb3dda56e757/candidate-analysis.json",
        "conversation": "artifacts/dialogues/7bbd1b0ccdb649edbaf2b64ccc9797e3/conversation-analysis-60f2c3fb3b8b/conversation-analysis.json",
    }
    now = datetime.now(timezone.utc)
    ui_evidence_path = "artifacts/ui/source-links-verification.json"
    ui_update = read(ui_evidence_path) if (ROOT / ui_evidence_path).exists() else None
    park_evidence_path = "artifacts/ui/park-scope-verification.json"
    park_update = read(park_evidence_path) if (ROOT / park_evidence_path).exists() else None
    azure_initial_ui_path = "artifacts/ui/azure-ui-initial-verification.json"
    azure_initial_ui = read(azure_initial_ui_path) if (ROOT / azure_initial_ui_path).exists() else None
    park_runs = []
    for folder in sorted((ROOT / "artifacts/park-scope").glob("*/summary.json")):
        summary = read(str(folder.relative_to(ROOT)))
        manifest = read(str(folder.with_name("manifest.json").relative_to(ROOT)))
        rows = []
        providers, returned_models, review_models, rerank_settings = set(), set(), set(), set()
        for row in read(str(folder.with_name("results.jsonl").relative_to(ROOT)), lines=True):
            trace = row.get("result", {})
            generation, review = trace.get("raw_response") or {}, trace.get("citation_review") or {}
            if generation.get("provider"):
                providers.add(generation["provider"])
            if generation.get("model"):
                returned_models.add(generation["model"])
            if review.get("model"):
                review_models.add(review["model"])
            if type(trace.get("rerank_enabled")) is bool:
                rerank_settings.add(trace["rerank_enabled"])
            pages = cited_source_pages(trace)
            for page in pages:
                for passage in page["passages"]:
                    passage.pop("text", None)
            rows.append({k: row.get(k) for k in ("dialogue_id", "turn", "park", "question", "expected_action", "operational_pass", "checks", "error")} | {
                "action": trace.get("response", {}).get("action"),
                "rendered": trace.get("rendered"), "sources_used": pages,
                "history_length": len(trace.get("history", [])),
                "guard_errors": trace.get("guard_errors", []),
                "review_error": review.get("error"),
                "generation": call_metadata(generation), "review": call_metadata(review),
                "elapsed_ms": trace.get("elapsed_ms"),
            })
        assert len(rows) == summary["attempts"]
        park_runs.append({"summary": summary, "manifest": manifest, "rows": rows,
                          "observed_generation_providers": sorted(providers),
                          "observed_returned_models": sorted(returned_models),
                          "observed_review_models": sorted(review_models),
                          "observed_rerank_settings": sorted(rerank_settings)})
    support_path = "artifacts/park-scope/support-observations.json"
    support_observations = read(support_path) if (ROOT / support_path).exists() else []
    for observation in support_observations:
        observed_result_path = f"artifacts/park-scope/{observation['run_id']}/results.jsonl"
        if observed_result_path in sources:
            assert observation["results_sha256"] == sources[observed_result_path]["sha256"]
        assert observation["human_review_pending"] is True
    support_audits = {}
    for audit_path in ("artifacts/park-scope/azure-support-audit.json",
                       "artifacts/park-scope/azure-support-audit-final.json"):
        if (ROOT / audit_path).exists():
            audit = read(audit_path)
            assert audit["results_sha256"] == sources[audit["results_path"]]["sha256"]
            assert audit["human_review_pending"] is True
            assert all(case["human_review_pending"] is True for case in audit["cases"])
            support_audits[audit_path] = audit
    retrieval_path = "artifacts/park-scope/retrieval-check.json"
    if (ROOT / retrieval_path).exists():
        retrieval_evidence[retrieval_path] = read(retrieval_path)
    config, pricing = read("config/project.json"), read("config/pricing.json")
    ledger_snapshots = [{"label": "Historical technical audit", "recorded_at": technical["cost"].get("last_event_utc"), "ledger": technical["cost"]}]
    for label, evidence_item, time_key in (
        ("Source-link UI check", ui_update, "verified_at_utc"),
        ("Park-selector UI check", park_update, "verified_at_utc"),
    ):
        if evidence_item and evidence_item.get("api_usage", {}).get("ledger_after"):
            ledger_snapshots.append({"label": label, "recorded_at": evidence_item.get(time_key), "ledger": evidence_item["api_usage"]["ledger_after"]})
    for run in park_runs:
        if run["summary"].get("api_usage", {}).get("ledger_after"):
            ledger_snapshots.append({"label": "Park-scope run " + run["summary"]["id"], "recorded_at": run["summary"]["completed_at"], "ledger": run["summary"]["api_usage"]["ledger_after"]})
    for path, smoke in setup_evidence.items():
        if smoke.get("ledger_after"):
            ledger_snapshots.append({"label": path, "recorded_at": smoke.get("checked_at_utc"), "ledger": smoke["ledger_after"]})
    latest_ledger = max(ledger_snapshots, key=lambda snapshot: snapshot["ledger"]["events"])
    data = {
        "generated_at_utc": now.isoformat(), "generated_at_local": now.astimezone(ZoneInfo("America/Chicago")).strftime("%b %d, %Y · %I:%M %p %Z"),
        "scope": "Local ParkGuide implementation and reused non-gold diagnostics; human course benchmark pending",
        "stage_audit": stages, "technical": technical, "corpus": corpus, "documents": documents,
        "builds": builds, "config": config, "pricing": pricing,
        "final_verification": read("artifacts/final-verification.json"), "reviews": review_details,
        "review_counts": review_counts, "analyses": {k: read(p) for k, p in analysis_paths.items()},
        "failure_proposals": failures, "evidence": evidence,
        "source_link_stats": dict(attribution), "source_link_update": ui_update,
        "park_scope_update": park_update, "park_scope_runs": park_runs,
        "park_support_observations": support_observations,
        "park_support_audits": support_audits, "azure_initial_ui_update": azure_initial_ui,
        "setup_evidence": setup_evidence, "retrieval_evidence": retrieval_evidence,
        "ledger_snapshots": ledger_snapshots, "latest_ledger_snapshot": latest_ledger,
        "source_manifest": list(sources.values()),
    }
    # Display proof offline; no remote image or font requests.
    img = ROOT / "artifacts/ui/cited-answer-and-refusal.jpg"
    data["screenshot"] = "data:image/jpeg;base64," + base64.b64encode(img.read_bytes()).decode()
    source_link_img = ROOT / "artifacts/ui/source-links-preview.png"
    if source_link_img.exists():
        data["source_link_screenshot"] = "data:image/png;base64," + base64.b64encode(source_link_img.read_bytes()).decode()
    park_img = ROOT / "artifacts/ui/park-selector-preview.png"
    if park_update and park_img.exists():
        data["park_scope_screenshot"] = "data:image/png;base64," + base64.b64encode(park_img.read_bytes()).decode()
    assert len(documents) == corpus["counts"]["usable_html"] + corpus["counts"]["usable_pdf"] == 155
    assert len(stages["stages"]) == 7
    assert sum(len(s["curated_rows"]) for s in stages["stages"]) == 305
    assert sum(x["total"] for x in review_counts.values()) == 66
    assert all(r["human_verifier"] is None for r in review_details)
    assert review_counts["B3"]["correct"] == 12 and review_counts["dialogues"]["uncertain"] == 2
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
    template = (OUT / "template.html").read_text()
    html = template.replace("__RUN_DATA__", payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(html)
    export = dict(data)
    export.pop("screenshot")
    export.pop("source_link_screenshot", None)
    export.pop("park_scope_screenshot", None)
    (OUT / "run-data.json").write_text(json.dumps(export, ensure_ascii=False, indent=2, allow_nan=False))
    print(f"Dashboard built: {len(documents)} documents; 7 stages; 305 attempted evaluations; 66 final AI labels; {len(sources)} provenance records.")


if __name__ == "__main__":
    build()
