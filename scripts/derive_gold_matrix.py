"""Freeze five independent labels, prepare source-based adjudication and score.

References and semantic judgments remain AI-provisional. Report generation uses
saved actual results and standard count-based action/retrieval metrics.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics

from gold_matrix import CONFIGS, DATA, ROOT, RUN, dump, readlines, sha, utc, validate
from evaluation_integrity import load_frozen_chunks, unique_rows, validate_frozen_inputs

NAMES = list(CONFIGS)
ACTIONS = ["answer", "refuse", "clarify"]


def classify(truth, predicted):
    if len(truth) != len(predicted):
        raise ValueError("Every expected action needs exactly one prediction")
    classes = []
    for name in ACTIONS:
        tp = sum(t == name and p == name for t, p in zip(truth, predicted))
        fp = sum(t != name and p == name for t, p in zip(truth, predicted))
        fn = sum(t == name and p != name for t, p in zip(truth, predicted))
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
        classes.append({"class": name, "tp": tp, "fp": fp, "fn": fn, "support": tp+fn, "precision": precision, "recall": recall, "f1": f1})
    tp = sum(row["tp"] for row in classes)
    # A wrong/failed single-label prediction contributes one FP and one FN.
    # Include an out-of-contract 'error' prediction in the global counts.
    fp = fn = len(truth) - tp
    return {"n": len(truth), "accuracy": sum(t == p for t, p in zip(truth, predicted))/len(truth) if truth else None,
            "macro_precision": statistics.mean(r["precision"] if r["precision"] is not None else 0 for r in classes),
            "macro_recall": statistics.mean(r["recall"] if r["recall"] is not None else 0 for r in classes),
            "macro_f1": statistics.mean(r["f1"] if r["f1"] is not None else 0 for r in classes),
            "micro_precision": tp/(tp+fp) if tp+fp else None, "micro_recall": tp/(tp+fn) if tp+fn else None,
            "micro_f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None, "per_class": classes,
            "macro_zero_policy": "undefined class value contributes zero to the three-class macro average; per-class undefined values remain null"}


def prepare_adjudication():
    packet = json.loads((DATA / "annotation-input.json").read_text())
    reviewers = {}
    hashes = {}
    for name in NAMES:
        validate(name)
        path = RUN / "reviewers" / name / "labels.json"
        raw_path = path.with_name("labels.raw.json")
        if not raw_path.exists(): raw_path.write_bytes(path.read_bytes())
        assert raw_path.read_bytes() == path.read_bytes()
        hashes[name] = sha(path)
        reviewers[name] = {r["item_id"]: r for r in json.loads(path.read_text())["labels"]}
    items = []
    for case in packet["cases"]:
        labels = {name: reviewers[name][case["item_id"]] for name in NAMES}
        votes = Counter(r["action"] for r in labels.values())
        top = votes.most_common(1)[0]
        items.append({**case, "action_votes": dict(votes), "majority_action": top[0] if top[1] >= 3 else None, "independent_labels": labels})
    instructions = """Derive 40 AI-consensus references using every independent label and the frozen sources. You are adjudicating semantic facts, not voting on prose. Do not read chatbot outputs, prior drafts or other repository evaluation results. Use only adjudication-input.json and the source text therein. Action must match the equal-weight unique majority unless an explicit source-backed override is necessary; expose every disagreement. Cluster synonyms into atomic facts. For each required fact, record supporting_labels as reviewer_id/fact_id pairs from the independent inputs and exact <=25-word source quote evidence groups (each inner group jointly supports the fact; different groups are alternatives). Require facts supported by at least 3 reviewers. A source-critical qualifier mentioned by fewer can be retained only with source_override=true and a documented reason, not by pretending votes. Minority incidental/optional facts may be recorded in optional_notes, not made mandatory. Derive expected_answer and behavior_requirements from all labels; require useful pass-detail clarification and qualified-clinician referral rather than imitate the current app. Never treat unavailable requested facts as factual reference evidence. Preserve tables, dates, exception/eligibility qualifiers and one-park scope. Use source headers/rows as needed. Return references (40 items) with item_id, action, answerability, expected_answer, required_facts (fact_id,text,supporting_labels,evidence_groups), behavior_requirements, forbidden_contradictions, optional_notes, disagreements (issue,reviewer_ids,resolution), adjudication_rationale, source_override (boolean). Do not invent human approval. No provider/app/browser calls or facts from memory. This is not an independent sixth labeling vote. Keep output concise, semantic and source-based. Write all 40 records; root will validate votes, IDs and quotes mechanically. You may inspect per-item subsets using Python to keep context manageable."""
    dump(RUN / "label-freeze.json", {"created_at": utc(), "input_sha256": sha(DATA / "annotation-input.json"), "label_hashes": hashes, "all_five_present": True, "human_review_pending": True})
    dump(RUN / "adjudication-input.json", {"instructions": instructions, "items": items, "sources": packet["sources"], "source_selection_limit": "Focused saved source packet; no output-dependent labels and no human verification."})
    (RUN / "adjudication-instructions.txt").write_text(instructions + "\n")
    print(json.dumps({"all_reviewers": 5, "labels": 200, "action_disagreements": sum(len(r["action_votes"])>1 for r in items)}))


def finalize():
    packet = json.loads((DATA / "annotation-input.json").read_text())
    sources = {s["source_id"]: s for s in packet["sources"]}
    cases = {c["item_id"]: c for c in packet["cases"]}
    lineage = {r["item_id"]: r for r in json.loads((DATA / "case-map.json").read_text())}
    votes = {r["item_id"]: r for r in json.loads((RUN / "adjudication-input.json").read_text())["items"]}
    frozen = json.loads((RUN / "label-freeze.json").read_text())
    for name, digest in frozen["label_hashes"].items(): assert sha(RUN / "reviewers" / name / "labels.json") == digest
    adjudication = RUN / "adjudication.frozen.json"
    if not adjudication.exists():
        adjudication.write_bytes((RUN / "adjudication.json").read_bytes())
    refs = json.loads(adjudication.read_text())["references"]
    assert len(refs) == 40 and {r["item_id"] for r in refs} == set(cases)
    records = []
    for ref in refs:
        item_id = ref["item_id"]
        assert ref["action"] in ACTIONS
        majority = votes[item_id]["majority_action"]
        assert ref["action"] == majority or ref["source_override"] and ref["adjudication_rationale"]
        fact_ids = set()
        flattened = {}
        facts = []
        for fact in ref["required_facts"]:
            assert fact["fact_id"] not in fact_ids and fact["text"]
            fact_ids.add(fact["fact_id"])
            supporters = set()
            for support in fact["supporting_labels"]:
                reviewer, fact_id = support["reviewer_id"], support["fact_id"]
                raw = votes[item_id]["independent_labels"][reviewer]
                assert fact_id in {f["fact_id"] for f in raw["required_facts"]}
                supporters.add(reviewer)
            assert len(supporters) >= 3 or ref["source_override"]
            groups = []
            for group in fact["evidence_groups"]:
                assert group
                units = []
                for ev in group:
                    source = sources[ev["source_id"]]
                    assert source["source_url"].startswith(f"https://www.nps.gov/{cases[item_id]['selected_park']}/planyourvisit/")
                    quote = ev["quote"]
                    assert quote and len(quote.split()) <= 25 and source["text"].count(quote) == 1, (item_id, quote)
                    start = source["text"].index(quote)
                    unit = {"source_id": ev["source_id"], "doc_id": source["doc_id"], "source_url": source["source_url"], "content_hash": source["content_hash"], "quote": quote, "start": start, "end": start+len(quote)}
                    flattened[(unit["doc_id"], unit["start"], unit["end"])] = unit
                    units.append(unit)
                groups.append(units)
            assert groups, item_id
            facts.append({**fact, "evidence_groups": groups, "supporter_count": len(supporters)})
        record = {**cases[item_id], **lineage[item_id], **ref, "required_facts": facts, "evidence": list(flattened.values()),
                  "action_votes": votes[item_id]["action_votes"], "labeler_count": 5, "label_hashes": frozen["label_hashes"],
                  "verification_status": "ai_consensus_human_review_pending", "human_verifier": None, "verified_at": None,
                  "benchmark_eligible": False, "reference_origin": "all five independent source-based labels plus explicit AI semantic adjudication; no chatbot output provided to adjudicator"}
        records.append(record)
    records.sort(key=lambda r: r["item_id"])
    target = DATA / "gold-consensus.jsonl"
    if target.exists(): raise SystemExit("Consensus already frozen; create a reviewed revision instead")
    target.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    dump(DATA / "consensus-manifest.json", {"created_at": utc(), "dataset_sha256": sha(target), "label_freeze_sha256": sha(RUN / "label-freeze.json"), "adjudication_sha256": sha(adjudication), "adjudication_artifact": str(adjudication.relative_to(ROOT)), "count": 40, "facts": sum(len(r["required_facts"]) for r in records), "actions": dict(Counter(r["action"] for r in records)), "source_overrides": [r["item_id"] for r in records if r["source_override"]], "status": "AI_CONSENSUS_HUMAN_REVIEW_PENDING", "benchmark_eligible": False, "human_verifier": None})
    print(json.dumps({"consensus": 40, "facts": sum(len(r["required_facts"]) for r in records), "actions": dict(Counter(r["action"] for r in records))}))


def aggregate_retrieval(per_item):
    """Chunk recall and evidence coverage have different eligible denominators."""
    retrieval = {}
    for k in [5, 20]:
        coverage_group = [r[f"retrieval_at_{k}"] for r in per_item if f"retrieval_at_{k}" in r]
        group = [r for r in coverage_group if r["recall"] is not None]
        hits, retrieved, relevant = (sum(r[n] for r in group) for n in ["tp", "retrieved", "relevant"])
        p = hits / retrieved if retrieved else None
        recall = hits / relevant if relevant else None
        covered = sum(r["facts_covered"] for r in coverage_group)
        fact_total = sum(r["facts_total"] for r in coverage_group)
        retrieval[f"at_{k}"] = {
            "items": len(group),
            "macro_precision": statistics.mean(x["precision"] for x in group) if group else None,
            "macro_recall": statistics.mean(x["recall"] for x in group) if group else None,
            "macro_f1": statistics.mean(x["f1"] for x in group) if group else None,
            "micro_precision": p, "micro_recall": recall,
            "micro_f1": 2 * hits / (retrieved + relevant) if retrieved + relevant else None,
            "tp": hits, "retrieved": retrieved, "known_relevant": relevant,
            "fact_evidence_coverage": statistics.mean(x["fact_evidence_coverage"] for x in coverage_group) if coverage_group else None,
            "fact_evidence_coverage_items": len(coverage_group),
            "facts_covered": covered, "facts_total": fact_total,
            "fact_evidence_coverage_micro": covered / fact_total if fact_total else None,
        }
    def mean(field):
        values = [r[field] for r in per_item if r.get(field) is not None]
        return {"mean": statistics.mean(values) if values else None, "denominator": len(values)}
    context = mean("generation_context_fact_evidence_coverage")
    context["facts_covered"] = sum(r.get("generation_context_facts_covered", 0) for r in per_item)
    context["facts_total"] = sum(r.get("generation_context_facts_total", 0) for r in per_item)
    context["micro"] = context["facts_covered"] / context["facts_total"] if context["facts_total"] else None
    retrieval.update(
        mrr=mean("mrr"), ndcg_at_10=mean("ndcg_at_10"), generation_context_fact_evidence_coverage=context,
        qrels_definition="A chunk is relevant if its actual source spans jointly cover all units in any evidence group for at least one required atomic fact. Qrels judge only declared evidence alternatives; not exhaustive human relevance judgments.",
        rankings_definition="@5/@20 use ranked candidates before generation-context pruning; actual generation contexts have a separate coverage metric.",
        evidence_coverage_definition="Macro averages every answerable case with required facts, including zero-known-qrel cases. Micro divides fully covered facts by all required facts. Combined chunks can cover evidence even when no individual chunk is relevant.",
        missing_qrels_items=[r["item_id"] for r in per_item if r.get("known_relevant_chunks") == 0],
    )
    return retrieval


def score(output_dir=None):
    output_dir = Path(output_dir) if output_dir is not None else RUN
    database = ROOT / "data/parkguide.sqlite"
    identities = validate_frozen_inputs(include_semantic=False, database=database, root=ROOT, data=DATA, run=RUN)
    from parkguide.evaluation import evidence_covered
    ref_rows = readlines(DATA / "gold-consensus.jsonl")
    bot_rows = readlines(RUN / "chatbot/responses.jsonl")
    refs = unique_rows(ref_rows, "references", count=40)
    bots = unique_rows(bot_rows, "responses", expected_ids=refs, count=40)
    labels = {}
    for name in NAMES:
        rows = json.loads((RUN / "reviewers" / name / "labels.json").read_text())["labels"]
        labels[name] = unique_rows(rows, name, expected_ids=refs, count=40)
    ids = sorted(refs)
    pairwise, loo = {}, {}
    for name in NAMES:
        pairwise[name] = {other: sum(labels[name][i]["action"] == labels[other][i]["action"] for i in ids)/40 for other in NAMES}
        truth, pred, excluded = [], [], []
        for i in ids:
            other_votes = Counter(labels[n][i]["action"] for n in NAMES if n != name)
            top = other_votes.most_common(1)[0]
            if top[1] < 3:
                excluded.append(i); continue
            truth.append(top[0]); pred.append(labels[name][i]["action"])
        loo[name] = {**classify(truth, pred), "excluded_no_other_reviewer_majority": excluded, "meaning": "agreement with the other four reviewers, not factual accuracy"}
    total_counts, within = Counter(), []
    for i in ids:
        counts = Counter(labels[n][i]["action"] for n in NAMES)
        total_counts.update(counts)
        within.append(sum(n*(n-1) for n in counts.values())/20)
    pbar = statistics.mean(within)
    expected = sum((n/200)**2 for n in total_counts.values())
    fact_representation = {name: {"represented": sum(any(s["reviewer_id"] == name for s in f["supporting_labels"]) for ref in refs.values() for f in ref["required_facts"]),
                                 "total": sum(len(ref["required_facts"]) for ref in refs.values()),
                                 "meaning": "Facts represented in this derived consensus; not independently established fact accuracy"} for name in NAMES}
    agreement = {"pairwise_action_agreement": pairwise, "leave_one_out_action_metrics": loo, "consensus_fact_representation": fact_representation, "fleiss_kappa": (pbar-expected)/(1-expected) if expected != 1 else None,
                 "unanimous_action_items": sum(len({labels[n][i]["action"] for n in NAMES}) == 1 for i in ids), "items": 40, "interpretation": "Agreement is correlated AI agreement, not human correctness; only action labels, not semantic facts, are compared numerically."}
    action = classify([refs[i]["action"] for i in ids], [bots[i].get("result", {}).get("response", {}).get("action", "error") for i in ids])
    build_id = identities["build_id"]
    universe = load_frozen_chunks(database, build_id)
    per_item, qrels = [], []
    for i in ids:
        ref, bot = refs[i], bots[i]
        row = {"item_id": i, "candidate_item_id": ref["candidate_item_id"], "expected_action": ref["action"], "actual_action": bot.get("result", {}).get("response", {}).get("action", "error"), "action_correct": ref["action"] == bot.get("result", {}).get("response", {}).get("action"), "error": bot.get("error")}
        result = bot.get("result", {})
        row["guard_errors"] = result.get("guard_errors", [])
        context_ids = {c["chunk_id"] for c in result.get("contexts", [])}
        claims = result.get("response", {}).get("claims", [])
        row["claim_identity"] = {"claims": len(claims), "valid": sum(bool(c.get("evidence_ids")) and all(x in context_ids for x in c["evidence_ids"]) for c in claims), "semantic_support": "assessed separately, not implied by identity"}
        if ref["action"] == "answer" and ref["required_facts"]:
            eligible = [c for c in universe if c["source_url"].startswith(f"https://www.nps.gov/{ref['selected_park']}/planyourvisit/")]
            def fact_in(fact, chunks):
                return any(all(evidence_covered(unit, chunks) for unit in group) for group in fact["evidence_groups"])
            relevant = {c["chunk_id"] for c in eligible if any(fact_in(f, [c]) for f in ref["required_facts"])}
            result = bot.get("result", {})
            ranked = result.get("retrieval", {}).get("reranked", []) or result.get("retrieval", {}).get("candidates", [])
            actual_contexts = result.get("contexts", [])
            qrels.append({"item_id": i, "build_id": build_id, "relevant_chunk_ids": sorted(relevant), "known_evidence_only": True})
            row["known_relevant_chunks"] = len(relevant)
            for k in [5, 20]:
                top = ranked[:k]
                hits = len({c["chunk_id"] for c in top} & relevant)
                p = hits/len(top) if top else 0.0
                r = hits/len(relevant) if relevant else None
                covered = sum(fact_in(f, top) for f in ref["required_facts"])
                row[f"retrieval_at_{k}"] = {"tp": hits, "retrieved": len(top), "relevant": len(relevant), "precision": p, "recall": r, "f1": 2*p*r/(p+r) if r is not None and p+r else 0.0 if r is not None else None,
                                            "fact_evidence_coverage": covered / len(ref["required_facts"]),
                                            "facts_covered": covered, "facts_total": len(ref["required_facts"])}
            row["generation_context_facts_covered"] = sum(fact_in(f, actual_contexts) for f in ref["required_facts"])
            row["generation_context_facts_total"] = len(ref["required_facts"])
            row["generation_context_fact_evidence_coverage"] = row["generation_context_facts_covered"] / row["generation_context_facts_total"]
            ordered = [c["chunk_id"] in relevant for c in ranked]
            row["mrr"] = next((1/(idx+1) for idx, hit in enumerate(ordered) if hit), 0) if relevant else None
            dcg = sum(int(v)/math.log2(idx+2) for idx, v in enumerate(ordered[:10]))
            ideal = sum(1/math.log2(idx+2) for idx in range(min(10,len(relevant))))
            row["ndcg_at_10"] = dcg/ideal if ideal else None
        per_item.append(row)
    retrieval = aggregate_retrieval(per_item)
    timings = [b["result"]["elapsed_ms"] for b in bots.values() if "result" in b]
    import numpy as np
    operational = {"attempted": len(refs), "raw_response_rows": len(bot_rows), "unique_response_ids": len(bots), "completed": len(timings), "errors": sum(bool(b.get("error")) for b in bots.values()), "guard_error_item_ids": [r["item_id"] for r in per_item if r["guard_errors"]], "latency_p50_ms": float(np.percentile(timings,50)) if timings else None, "latency_p95_ms": float(np.percentile(timings,95)) if timings else None,
                   "latency_policy": "successful calls including preflight; errors counted separately, never zero latency"}
    summary = {"created_at": utc(), "dataset_sha256": identities["dataset_sha256"], "responses_sha256": identities["responses_sha256"], "frozen_inputs": identities, "agreement": agreement, "action_metrics": action, "retrieval_metrics": retrieval, "operational": operational,
               "grading_status": "AI_CONSENSUS_REFERENCE_HUMAN_REVIEW_PENDING", "formal_course_benchmark": False}
    dump(output_dir / "agreement.json", agreement)
    dump(output_dir / "metrics.json", summary)
    dump(output_dir / "qrels.json", {"build_id": build_id, "definition": retrieval["qrels_definition"], "queries": qrels})
    (output_dir / "per-item-metrics.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in per_item))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=["prepare-adjudication", "finalize", "score"])
    op = p.parse_args().operation
    result = {"prepare-adjudication": prepare_adjudication, "finalize": finalize, "score": score}[op]()
    if result is not None:
        print(json.dumps(result))


if __name__ == "__main__": main()
