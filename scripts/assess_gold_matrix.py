"""Prepare and verify a source-based AI semantic assessment of saved responses.

No provider calls. The reference is frozen before exposing it to this assessor.
Semantic results remain provisional and cannot approve the course benchmark.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json

from gold_matrix import DATA, RUN, dump, readlines, sha, utc

INSTRUCTIONS = """Assess all 40 saved responses using only this packet and its frozen sources. Do not read old reports, the application's review verdicts, or relabel the reference. No provider, application, browser or network calls. Judge meaning, not lexical overlap. For each required fact assign covered/missing/contradicted/uncertain; for every behavior requirement assign satisfied/missing/uncertain. Include an exact response quote when covered/satisfied, otherwise explain the omission. Check every delivered claim against its actual cited passages, including conditions and exceptions: supported/unsupported/contradicted/uncertain. A source URL alone is insufficient; uncited reference sources cannot rescue a claim. Record source_id or cited chunk_id and exact source quotes in source_evidence. Separately flag unsupported factual assertions in the answer outside delivered claims. Respect saved-date scope, table headers, blank cells, permission conditions, and selected park. Refusals need substantive source-limit handling, medical referrals and useful pass clarification where required. Do not impose optional reference details. Never infer reviewer false rejection without pre-review candidates. Return assessments, one per item with item_id; facts [{fact_id,status,response_quote,reason}]; behaviors [{requirement_index,status,response_quote,reason}]; claims [{claim_index,status,source_evidence:[{chunk_id,quote}],reason}]; additional_answer_issues [{response_quote,reason}]; notes. Empty arrays for inapplicable dimensions. Every judgment is AI provisional and human review pending."""


def prepare():
    ref_rows = readlines(DATA / "gold-consensus.jsonl")
    bot_rows = readlines(RUN / "chatbot/responses.jsonl")
    assert len(ref_rows) == len({r["item_id"] for r in ref_rows}) == 40
    assert len(bot_rows) == len({r["item_id"] for r in bot_rows}) == 40
    refs = {r["item_id"]: r for r in ref_rows}
    bots = {r["item_id"]: r for r in bot_rows}
    assert set(refs) == set(bots) and len(refs) == 40
    cases = []
    for item_id, ref in sorted(refs.items()):
        bot = bots[item_id]
        result = bot.get("result", {})
        response = result.get("response", {})
        contexts = [{k: c[k] for k in ["chunk_id", "doc_id", "source_url", "content_hash", "text"]} for c in result.get("contexts", [])]
        cases.append({"item_id": item_id, "question": ref["question"], "selected_park": ref["selected_park"],
                      "reference": {k: ref[k] for k in ["action", "expected_answer", "required_facts", "behavior_requirements", "forbidden_contradictions", "optional_notes"]},
                      "actual_response": {k: response.get(k) for k in ["action", "answer", "claims"]},
                      "cited_passages": contexts, "error": bot.get("error")})
    path = RUN / "semantic-input.json"
    if path.exists(): raise SystemExit("Semantic input already frozen")
    packet = json.loads((DATA / "annotation-input.json").read_text())
    dump(path, {"instructions": INSTRUCTIONS, "reference_sha256": sha(DATA / "gold-consensus.jsonl"), "responses_sha256": sha(RUN / "chatbot/responses.jsonl"), "cases": cases, "sources": packet["sources"], "status": "AI_PROVISIONAL_HUMAN_REVIEW_PENDING"})
    (RUN / "semantic-instructions.txt").write_text(INSTRUCTIONS + "\n")
    print(json.dumps({"cases": len(cases), "input_sha256": sha(path)}))


def summarize():
    packet = json.loads((RUN / "semantic-input.json").read_text())
    assert packet["reference_sha256"] == sha(DATA / "gold-consensus.jsonl")
    assert packet["responses_sha256"] == sha(RUN / "chatbot/responses.jsonl")
    cases = {c["item_id"]: c for c in packet["cases"]}
    judged = json.loads((RUN / "semantic-assessment.json").read_text())["assessments"]
    assert len(judged) == len(cases) and {r["item_id"] for r in judged} == set(cases)
    facts, behaviors, claims = Counter(), Counter(), Counter()
    passing, failed, uncertain, identities, issue_items = [], [], [], [], []
    for row in judged:
        case = cases[row["item_id"]]
        response = case["actual_response"]
        text = response.get("answer") or ""
        required = case["reference"]["required_facts"]
        assert len(row["facts"]) == len(required) and {f["fact_id"] for f in row["facts"]} == {f["fact_id"] for f in required}
        expected_behavior = case["reference"]["behavior_requirements"]
        assert len(row["behaviors"]) == len(expected_behavior) and {b["requirement_index"] for b in row["behaviors"]} == set(range(len(expected_behavior)))
        actual_claims = response.get("claims") or []
        assert len(row["claims"]) == len(actual_claims) and {c["claim_index"] for c in row["claims"]} == set(range(len(actual_claims)))
        for fact in row["facts"]:
            assert fact["status"] in ["covered", "missing", "contradicted", "uncertain"]
            if fact["status"] == "covered": assert fact["response_quote"] and fact["response_quote"] in text
            facts[fact["status"]] += 1
        for behavior in row["behaviors"]:
            assert behavior["status"] in ["satisfied", "missing", "uncertain"]
            if behavior["status"] == "satisfied": assert behavior["response_quote"] and behavior["response_quote"] in text
            behaviors[behavior["status"]] += 1
        contexts = {c["chunk_id"]: c for c in case["cited_passages"]}
        for judgment in row["claims"]:
            assert judgment["status"] in ["supported", "unsupported", "contradicted", "uncertain"]
            claim = actual_claims[judgment["claim_index"]]
            valid = bool(claim.get("evidence_ids")) and all(i in contexts for i in claim["evidence_ids"])
            identities.append(valid)
            if judgment["status"] == "supported": assert valid and judgment["source_evidence"]
            for ev in judgment["source_evidence"]:
                assert ev["chunk_id"] in claim.get("evidence_ids", [])
                assert ev["quote"] and ev["quote"] in contexts[ev["chunk_id"]]["text"]
                assert len(ev["quote"].split()) <= 25
            claims[judgment["status"]] += 1
        for issue in row["additional_answer_issues"]:
            assert issue["response_quote"] and issue["response_quote"] in text
        good = (response.get("action") == case["reference"]["action"] and not case["error"]
                and all(f["status"] == "covered" for f in row["facts"])
                and all(b["status"] == "satisfied" for b in row["behaviors"])
                and all(c["status"] == "supported" for c in row["claims"])
                and not row["additional_answer_issues"])
        (passing if good else failed).append(row["item_id"])
        if any(x["status"] == "uncertain" for dimension in ["facts", "behaviors", "claims"] for x in row[dimension]): uncertain.append(row["item_id"])
        if row["additional_answer_issues"]: issue_items.append(row["item_id"])
    summary = {"created_at": utc(), "cases": 40, "facts": dict(facts), "fact_total": sum(facts.values()),
               "required_fact_coverage": facts["covered"] / sum(facts.values()) if facts else None,
               "behaviors": dict(behaviors), "behavior_total": sum(behaviors.values()),
               "behavior_satisfaction": behaviors["satisfied"] / sum(behaviors.values()) if behaviors else None,
               "delivered_claims": dict(claims), "claim_total": sum(claims.values()),
               "claim_citation_identity_valid": {"valid": sum(identities), "total": len(identities)},
               "claim_citation_semantic_support": claims["supported"] / sum(claims.values()) if claims else None,
               "full_rubric_pass": {"passed": len(passing), "total": 40, "item_ids": passing}, "not_full_pass_item_ids": failed,
               "uncertain_item_ids": uncertain, "additional_answer_issue_item_ids": issue_items,
               "input_sha256": sha(RUN / "semantic-input.json"), "assessment_sha256": sha(RUN / "semantic-assessment.json"),
               "status": "ONE_AI_ASSESSOR_PROVISIONAL_HUMAN_REVIEW_PENDING", "human_verified": False,
               "interpretation": "Exact quotes and identities validated mechanically; semantic labels from one AI assessor, not calibrated human correctness. Uncertain labels count as not passed. Citation support is claim precision only; unsupported-claim recall/F1 cannot be measured without an independently labeled candidate universe."}
    dump(RUN / "semantic-summary.json", summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare", "summarize"])
    args = parser.parse_args()
    {"prepare": prepare, "summarize": summarize}[args.operation]()
