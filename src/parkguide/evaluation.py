"""Saved-result evaluation, immutable runs, and protected final-test gates."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from .chat import answer
from .runtime import ROOT, config, digest, read_jsonl, write_jsonl

CATEGORIES = {"factual": 15, "multi_hop": 6, "comparative": 4, "temporal": 4, "unanswerable": 8, "ambiguous_adversarial": 3}
DEV_QUOTAS = {"factual": 9, "multi_hop": 4, "comparative": 2, "temporal": 2, "unanswerable": 5, "ambiguous_adversarial": 2}


def validate_gold(rows, require_human=False):
    if len(rows) != 40 or len({row["item_id"] for row in rows}) != 40:
        raise ValueError("Gold needs exactly 40 unique records")
    for category, count in CATEGORIES.items():
        if sum(row["category"] == category for row in rows) != count:
            raise ValueError(f"Gold category quota mismatch: {category}")
    for row in rows:
        if row.get("expected_action") not in ("answer", "clarify", "refuse"):
            raise ValueError("Gold action is invalid")
        if row["expected_action"] == "answer" and not row.get("evidence"):
            raise ValueError("Answerable gold needs source spans")
        for evidence in row.get("evidence", []):
            if not all(key in evidence for key in ("doc_id", "content_hash", "start", "end")) or evidence["end"] <= evidence["start"]:
                raise ValueError("Gold evidence span is invalid")
        if require_human and not (row.get("verification_status") == "human_verified" and row.get("human_verifier") and row.get("verified_at")):
            raise RuntimeError("HUMAN_REVIEW_PENDING: every gold record needs actual human verification")


def seal_drafts(path):
    rows = read_jsonl(path)
    validate_gold(rows)
    folder = ROOT / "data/evaluation"
    folder.mkdir(parents=True, exist_ok=True)
    canonical = folder / "gold-drafts.jsonl"
    if Path(path).resolve() != canonical.resolve():
        write_jsonl(canonical, rows, exclusive=True)
    existing=folder/'gold-draft-manifest.json'
    if existing.exists():
        original=json.loads(existing.read_text())
        if hashlib.sha256(canonical.read_bytes()).hexdigest()!=original['sha256']:
            raise RuntimeError('Original authoring seal is immutable; use gold-split after actual human verification to record the reviewed revision')
        return original
    metadata = {"count": 40, "sha256": hashlib.sha256(canonical.read_bytes()).hexdigest(), "frozen_at": datetime.now(timezone.utc).isoformat(), "status": "HUMAN_REVIEW_PENDING", "chatbot_outputs_seen_before_authoring": False}
    # This records the documented workflow; callers must not fabricate authorship.
    (folder / "gold-draft-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def split_gold(path):
    rows = read_jsonl(path)
    validate_gold(rows, require_human=True)
    folder = ROOT / "data/evaluation"
    if Path(path).resolve()!=(folder/'gold-drafts.jsonl').resolve():
        raise ValueError('Review the canonical sealed gold-drafts.jsonl before splitting')
    authoring=json.loads((folder/'gold-draft-manifest.json').read_text())
    if any((folder/name).exists() for name in ('dev.jsonl','sealed-test.jsonl','split-manifest.json')):
        raise RuntimeError('The development/test split is already frozen')
    families = [row.get('family_id',row['item_id']) for row in rows]
    if len(families)!=len(set(families)):
        raise ValueError('Dependent families across categories require an explicit reviewed split')
    random = np.random.default_rng(config()["evaluation"]["split_seed"])
    development, test = [], []
    for category, quota in DEV_QUOTAS.items():
        group = [row for row in rows if row["category"] == category]
        families = [row.get("family_id", row["item_id"]) for row in group]
        if len(families) != len(set(families)):
            raise ValueError("Dependent families require an explicit reviewed split to preserve quotas")
        order = random.permutation(len(group))
        development.extend(group[position] for position in order[:quota])
        test.extend(group[position] for position in order[quota:])
    write_jsonl(folder / "dev.jsonl", development, exclusive=True)
    write_jsonl(folder / "sealed-test.jsonl", test, exclusive=True)
    manifest = {"dev_hash": digest(development), "test_hash": digest(test), "seed": config()["evaluation"]["split_seed"], "dev_count": 24, "test_count": 16}
    (folder / "split-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    reviewed={'count':40,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'original_authoring_sha256':authoring['sha256'],'original_frozen_at':authoring['frozen_at'],'reviewed_at':datetime.now(timezone.utc).isoformat(),'status':'human_verified'}
    (folder/'gold-reviewed-manifest.json').write_text(json.dumps(reviewed,indent=2)+'\n')
    return manifest


def _spans(chunk):
    span = chunk.get("source_span", chunk.get("source_span_json", []))
    if isinstance(span, str):
        span = json.loads(span)
    if isinstance(span, dict):
        span = span.get("spans", [span])
    return span


def evidence_covered(evidence, chunks):
    intervals = []
    for chunk in chunks:
        if chunk["doc_id"] != evidence["doc_id"]:
            continue
        if evidence.get("content_hash") and chunk.get("content_hash") != evidence["content_hash"]:
            continue
        for span in _spans(chunk):
            start, end = span.get("start", 0), span.get("end", 0)
            if end > evidence["start"] and start < evidence["end"]:
                intervals.append((start, end))
    cursor = evidence["start"]
    for start, end in sorted(intervals):
        if start > cursor:
            break
        cursor = max(cursor, end)
    return cursor >= evidence["end"]


def retrieval_metrics(item, ranked, universe):
    evidence = item.get("evidence", [])
    if not evidence:
        return {key: None for key in ("recall_5", "recall_20", "mrr", "ndcg_10", "evidence_coverage_5", "evidence_coverage_20")}
    relevant = {chunk["chunk_id"] for chunk in universe if any(evidence_covered(unit, [chunk]) for unit in evidence)}
    ranked_relevance = [chunk["chunk_id"] in relevant for chunk in ranked]
    def recall(k):
        return sum(ranked_relevance[:k]) / len(relevant) if relevant else None
    dcg = sum(int(hit) / math.log2(index + 2) for index, hit in enumerate(ranked_relevance[:10]))
    ideal = sum(1 / math.log2(index + 2) for index in range(min(10, len(relevant))))
    return {"recall_5": recall(5), "recall_20": recall(20), "mrr": next((1 / (index + 1) for index, hit in enumerate(ranked_relevance) if hit), 0) if relevant else None, "ndcg_10": dcg / ideal if ideal else None,
            "evidence_coverage_5": sum(evidence_covered(unit, ranked[:5]) for unit in evidence) / len(evidence),
            "evidence_coverage_20": sum(evidence_covered(unit, ranked[:20]) for unit in evidence) / len(evidence)}


def provisional_grade(item, result):
    response = result["response"]
    text = response.get("answer", "") + " " + " ".join(claim.get("text", "") for claim in response.get("claims", []))
    tokens = set(re.findall(r"\w+", text.lower()))
    required = item.get("required_facts", [])
    # A visible diagnostic signal only. Humans confirm facts/contradictions/support.
    hits = []
    for fact in required:
        terms = set(re.findall(r"\w+", (fact if isinstance(fact, str) else fact["text"]).lower()))
        hits.append(len(terms & tokens) / max(len(terms), 1) >= 0.65)
    action_correct = response.get("action") == item["expected_action"]
    claims = response.get("claims", [])
    allowed = {chunk["chunk_id"] for chunk in result["contexts"]}
    identities_valid = all(claim.get("evidence_ids") and all(identifier in allowed for identifier in claim["evidence_ids"]) for claim in claims)
    return {"action_correct": action_correct, "fact_coverage_heuristic": sum(hits) / len(hits) if hits else None,
            "diagnostic_pass": action_correct and (all(hits) if required else True) and not result["guard_errors"],
            "citation_identity_valid": identities_valid if claims and not result.get("closed_book") else None,
            "citation_semantic_support": None, "human_grade": None,
            "grading_status": "PROVISIONAL_LEXICAL_DIAGNOSTIC_NOT_SEMANTIC_ACCURACY"}


def summarize(rows):
    summary = {"items": len(rows), "errors": sum("error" in row for row in rows), "grading_status": "HUMAN_REVIEW_PENDING"}
    successful = [row for row in rows if "result" in row]
    for metric in ("recall_5", "recall_20", "mrr", "ndcg_10", "evidence_coverage_5", "evidence_coverage_20"):
        values = [row["metrics"][metric] for row in successful if row["metrics"].get(metric) is not None]
        summary[metric] = {"mean": float(np.mean(values)) if values else None, "denominator": len(values)}
    summary["diagnostic_passes"] = sum(row["grade"]["diagnostic_pass"] for row in successful)
    summary["action_correct"] = sum(row["grade"]["action_correct"] for row in successful)
    times = [row["result"]["elapsed_ms"] for row in successful]
    summary["latency_p50_ms"] = float(np.percentile(times, 50)) if times else None
    summary["latency_p95_ms"] = float(np.percentile(times, 95)) if times else None
    summary["latency_denominator"] = len(times)
    summary["latency_failure_policy"] = "Completed responses only; failed requests are counted separately, not assigned zero latency"
    summary["generation_cost_estimate_usd"] = sum(row["result"]["response"].get("cost_estimate_usd", 0) for row in successful)
    summary["generation_cost_denominator"] = len(successful)
    summary["generation_cost_scope"] = "Successful generation and successful claim-review calls only; excludes query embeddings and failed-call reservations. Whole implementation cost is in the API ledger."
    summary["answer_accuracy"] = None
    summary["citation_semantic_support"] = None
    return summary


def paired_bootstrap(before, after, seed=633, samples=10000):
    before, after = np.asarray(before, dtype=float), np.asarray(after, dtype=float)
    if before.shape != after.shape or not len(before):
        raise ValueError("Paired samples must share item IDs and be nonempty")
    difference = after - before
    draws = np.random.default_rng(seed).integers(0, len(before), (samples, len(before)))
    low, high = np.percentile(difference[draws].mean(axis=1), [2.5, 97.5])
    return {"difference": float(difference.mean()), "ci95": [float(low), float(high)], "established_lift": bool(low > 0), "seed": seed, "samples": samples}


def run(dataset_path, configurations, *, diagnostic=False, final=False):
    from .store import load_chunks
    items = read_jsonl(dataset_path)
    final_folder = _final_gate(dataset_path, configurations) if final else None
    if not diagnostic:
        for item in items:
            if item.get("verification_status") != "human_verified":
                raise RuntimeError("HUMAN_REVIEW_PENDING; only separately labeled diagnostics are allowed")
    if "sealed-test" in str(dataset_path) and not final:
        raise RuntimeError("Sealed test cannot be used for development")
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    folder = final_folder or ROOT / "artifacts/runs" / identifier
    folder.mkdir(parents=True, exist_ok=final)
    if diagnostic:
        gold = read_jsonl(ROOT / "data/evaluation/gold-drafts.jsonl")
        protected = {row['question'].strip().lower() for row in gold}
        if any(item.get('benchmark_eligible') is not False or item.get('verification_status') != 'diagnostic_unverified' or item['question'].strip().lower() in protected for item in items):
            raise ValueError('Diagnostics must be separate, non-gold, explicitly unverified questions')
    manifest = {"kind": "final_test" if final else "non_gold_diagnostic" if diagnostic else "development", "dataset_hash": digest(items), "config_hash": digest(config()), "code_hash": code_hash(), "configurations": configurations, "request_concurrency": 2, "latency_policy": "two concurrent queries per variant; measured end-to-end with cache state retained"}
    if not final:
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    output = folder / "results.jsonl"
    rows = read_jsonl(output) if final and output.exists() else []
    completed = {(row["configuration"], row["item_id"]) for row in rows}
    for variant in configurations:
        universe = load_chunks(ROOT / config()["database"], variant.get("build_id"))
        def process(item):
            row = {"item_id": item["item_id"], "configuration": variant["name"], "expected_action": item["expected_action"]}
            try:
                result = answer(item["question"], mode=variant.get("mode", "hybrid"), build_id=variant.get("build_id"), rerank=variant.get("rerank", False), closed_book=variant.get("closed_book", False))
                ranked = result["retrieval"].get("reranked", result["retrieval"]["candidates"])
                metrics = retrieval_metrics(item, ranked, universe)
                units=item.get('evidence',[])
                metrics['selected_context_evidence_coverage']=sum(evidence_covered(unit,result['contexts']) for unit in units)/len(units) if units else None
                if variant.get("closed_book"):
                    metrics = {key: None for key in metrics}
                row.update(result=result, metrics=metrics, grade=provisional_grade(item, result))
            except Exception as error:
                row["error"] = {"type": type(error).__name__, "message": str(error) if isinstance(error, (RuntimeError, ValueError)) else "Provider or pipeline failure; sensitive details suppressed"}
            return row
        remaining = [item for item in items if (variant["name"], item["item_id"]) not in completed]
        with ThreadPoolExecutor(max_workers=2) as executor:
            for future in as_completed([executor.submit(process, item) for item in remaining]):
                row = future.result()
                with output.open("a") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                rows.append(row)
                print(f"{variant['name']} {row['item_id']}: {'ERROR' if 'error' in row else row['result']['response']['action']}", flush=True)
    summaries = {variant["name"]: summarize([row for row in rows if row["configuration"] == variant["name"]]) for variant in configurations}
    (folder / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    review_path = folder / 'human-review.jsonl'
    annotations = read_jsonl(review_path) if review_path.exists() else []
    reviewed = {(row['configuration'], row['item_id']) for row in annotations}
    annotations.extend({"item_id": row["item_id"], "configuration": row["configuration"], "human_grade": None, "failure_class": None, "verified_by": None} for row in rows if (row['configuration'], row['item_id']) not in reviewed)
    write_jsonl(review_path, annotations)
    return {"run": str(folder), "summaries": summaries}


def code_hash():
    return digest({str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((ROOT / 'src').rglob('*.py'))})


def final_snapshot(dataset_path, configurations):
    from .store import _connection, get_manifest
    database = ROOT / config()['database']
    identities = {}
    # Manifests describe the original build. Deletions or changed stored rows
    # must invalidate acceptance even when the original manifest is unchanged.
    with _connection(database) as connection:
        for build in {variant['build_id'] for variant in configurations}:
            chunks=[dict(row) for row in connection.execute('SELECT * FROM chunks WHERE build_id=? ORDER BY chunk_id',(build,))]
            vectors=[{'chunk_id':row['chunk_id'],'dimension':row['dimension'],'sha256':hashlib.sha256(row['vector_f32']).hexdigest()} for row in connection.execute('SELECT * FROM embeddings WHERE build_id=? ORDER BY chunk_id',(build,))]
            documents=[dict(row) for row in connection.execute('SELECT * FROM documents WHERE doc_id IN (SELECT doc_id FROM chunks WHERE build_id=?) ORDER BY doc_id',(build,))]
            identities[build]={'manifest_hash':digest(get_manifest(database,build)), 'live_hash':digest({'chunks':chunks,'vectors':vectors,'documents':documents}), 'chunk_count':len(chunks),'vector_count':len(vectors)}
    return {"dataset_hash": digest(read_jsonl(dataset_path)), "config_hash": digest(config()), "code_hash": code_hash(),
            "builds": {variant["name"]: identities[variant['build_id']] for variant in configurations}, "configurations": configurations}


def _final_gate(dataset_path, configurations):
    folder = ROOT / "data/evaluation"
    acceptance_path = folder / "dev-acceptance.json"
    if not acceptance_path.exists():
        raise RuntimeError("HUMAN_REVIEW_PENDING: reviewed development acceptance is required before final test")
    acceptance = json.loads(acceptance_path.read_text())
    if not (acceptance.get("human_verifier") and acceptance.get("verified_at") and acceptance.get("all_gates_passed") is True):
        raise RuntimeError("HUMAN_REVIEW_PENDING: development gates are not confirmed")
    if Path(dataset_path).resolve() != (folder / "sealed-test.jsonl").resolve():
        raise ValueError("Final test must use the frozen held-out dataset")
    items = read_jsonl(dataset_path)
    if len(items) != 16 or any(row.get("verification_status") != "human_verified" or not row.get("human_verifier") or not row.get("verified_at") for row in items):
        raise RuntimeError("HUMAN_REVIEW_PENDING: all 16 test items need source verification")
    split = json.loads((folder / "split-manifest.json").read_text())
    if digest(items) != split["test_hash"] or len(configurations)!=4 or {variant["name"] for variant in configurations} != {"B0", "B1", "B2", "B3"}:
        raise ValueError("Final dataset/configuration does not match frozen B0–B3 plan")
    frozen = final_snapshot(dataset_path, configurations)
    development = read_jsonl(folder / 'dev.jsonl')
    if acceptance.get('accepted_snapshot_hash') != digest(frozen) or acceptance.get('accepted_dev_hash') != digest(development) or digest(development) != split['dev_hash']:
        raise RuntimeError('Development approval does not match current code/config/builds/datasets')
    destination = ROOT / "artifacts/final-test"
    destination.mkdir(parents=True, exist_ok=True)
    lock = destination / "manifest.json"
    if lock.exists():
        if json.loads(lock.read_text()) != frozen:
            raise RuntimeError("Final test is already frozen; changed code/config/data cannot be rerun")
    else:
        lock.write_text(json.dumps(frozen, indent=2) + "\n")
    return destination


def final_configurations():
    fixed = json.loads((ROOT / "artifacts/builds/fixed.json").read_text())["build_id"]
    structure = json.loads((ROOT / "artifacts/builds/structure.json").read_text())["build_id"]
    variants = [{"name": "B0", "build_id": fixed, "closed_book": True},
                {"name": "B1", "build_id": fixed, "mode": "bm25", "rerank": False},
                {"name": "B2", "build_id": fixed, "mode": "dense", "rerank": False},
                {"name": "B3", "build_id": structure, "mode": "hybrid", "rerank": config()['retrieval'].get('default_rerank',True)}]
    return variants


def final_batch():
    return run(ROOT / "data/evaluation/sealed-test.jsonl", final_configurations(), final=True)


def dialogues(path, *, mode="hybrid", build_id=None, rerank=None):
    if rerank is None:
        rerank = config()['retrieval'].get('default_rerank', False)
    definitions = read_jsonl(path)
    if len(definitions) < 6 or any(len(dialogue["turns"]) < 3 for dialogue in definitions):
        raise ValueError("Need six dialogues of at least three user turns")
    folder = ROOT / "artifacts/dialogues" / uuid.uuid4().hex
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({"kind": "non_gold_dialogue_diagnostic", "dataset_hash": digest(definitions), "config_hash": digest(config()), "code_hash":code_hash(), "mode": mode, "build_id": build_id, "rerank": rerank, "history": "actual preceding assistant responses; per-turn snapshot", "latency_policy":"sequential turns; query embedding cache retained"}, indent=2) + "\n")
    rows = []
    for dialogue in definitions:
        history = []
        for index, turn in enumerate(dialogue["turns"], 1):
            question = turn["question"] if isinstance(turn, dict) else turn
            try:
                result = answer(question, history, mode=mode, build_id=build_id, rerank=rerank)
            except Exception as error:
                rows.append({"dialogue_id": dialogue["dialogue_id"], "turn": index, "expected_action": turn.get("expected_action") if isinstance(turn, dict) else None, "error": {"type": type(error).__name__, "message": str(error) if isinstance(error, (RuntimeError, ValueError)) else "Provider or pipeline failure; sensitive details suppressed"}, "grading_status": "PIPELINE_ERROR"})
                write_jsonl(folder / "results.jsonl", rows)
                print(f"Dialogue {dialogue['dialogue_id']} turn {index}: ERROR", flush=True)
                # No canned assistant response or failed user turn is added.
                continue
            rows.append({"dialogue_id": dialogue["dialogue_id"], "turn": index, "expected_action": turn.get("expected_action") if isinstance(turn, dict) else None, "result": result, "grade": provisional_grade(turn, result) if isinstance(turn, dict) else None, "semantic_grade": None, "grading_status": "HUMAN_REVIEW_PENDING"})
            history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": result["rendered"]}])
            write_jsonl(folder / "results.jsonl", rows)
            print(f"Dialogue {dialogue['dialogue_id']} turn {index}: {result['response']['action']}", flush=True)
    return {"folder": str(folder), "dialogues": len(definitions), "attempted_turns": len(rows), "actual_turns": sum('result' in row for row in rows), "errors": sum('error' in row for row in rows), "grading_status": "HUMAN_REVIEW_PENDING"}
