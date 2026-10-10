"""Prepare an unverified, single-park revision; never call the chatbot/provider.

The sealed original drafts and independent corpus-labeling study are inputs only.
This revision is not eligible for the course benchmark or the legacy eval runner.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/evaluation/product-scope-v1"
ORIGINAL_SHA = "15117b5270cf0ffee2917b5fa2ab87496e3be4628860cda7bf77e6b933a8de47"
DB_SHA = "2e017b08ae4a358944716da3b62357b70c988bb61feebe62c39b9b0160feba5c"
PARKS = {"yose": "Yosemite", "yell": "Yellowstone", "grca": "Grand Canyon"}
PARK_ASSIGNMENTS = (
    ["yose"] * 5 + ["yell"] * 5 + ["grca"] * 5
    + ["yose", "yose", "yell", "yell", "grca", "grca"]
    + ["yell", "yose", "grca", "yose"]
    + ["yose", "yell", "grca", "grca"]
    + ["yose", "yell", "grca", "yell", "yell", "grca", "yose", "yell"]
    + ["yose", "yose", "grca"]
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save_lines(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-draft", action="store_true", help="Regenerate only this unverified revision's five owned outputs")
    args = parser.parse_args()
    if OUT.exists():
        if not args.refresh_draft:
            raise SystemExit("Refusing to overwrite an existing revision without --refresh-draft")
        previous = json.loads((OUT / "manifest.json").read_text())
        assert previous["status"] == "HUMAN_REVIEW_PENDING" and previous["benchmark_eligible"] is False
        for path in OUT.glob("*.jsonl"):
            assert all(row.get("verification_status") == "human_review_pending" for row in load_lines(path))
    original_path = ROOT / "data/evaluation/gold-drafts.jsonl"
    db_path = ROOT / "data/parkguide.sqlite"
    assert sha(original_path) == ORIGINAL_SHA and sha(db_path) == DB_SHA
    originals = load_lines(original_path)
    assert len(originals) == len(PARK_ASSIGNMENTS) == 40
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    docs = {}
    for row in conn.execute("SELECT * FROM documents"):
        docs[row["source_url"]] = (dict(row), json.loads(row["normalized_blocks_json"]))

    def evidence(park, page, quote):
        row, parsed = docs[f"https://www.nps.gov/{park}/planyourvisit/{page}.htm"]
        text = parsed["normalized_text"]
        assert hashlib.sha256(text.encode()).hexdigest() == row["content_hash"]
        assert text.count(quote) == 1 and len(quote.split()) <= 25, quote
        start = text.index(quote)
        block = next(b for b in parsed["blocks"] if b["start"] <= start < b["end"])
        return {"doc_id": row["doc_id"], "source_url": row["source_url"],
                "content_hash": row["content_hash"], "quote": quote,
                "start": start, "end": start + len(quote), "heading_path": block["heading_path"]}

    created = datetime.now(timezone.utc).isoformat()

    def candidate(original, item_id, park):
        row = deepcopy(original)
        row.update(item_id=item_id, selected_park=park, benchmark_eligible=False,
                   verification_status="human_review_pending", human_verifier=None, verified_at=None)
        row["original_item_id"] = original["item_id"]
        row["original_question"] = original["question"]
        row["original_authorship"] = row.pop("authorship", None)
        row["authorship"] = {"created_at": created, "method": "AI product-scope revision from captured sources and current code; after earlier development outputs", "model_output_seen": True}
        row["grading_contract"] = "Semantic required facts, behavior requirements, contradictions and claim source support; never literal substring grading."
        row["behavior_requirements"] = ["Keep this chat scoped to its selected park.", "Do not present captured schedules or statuses as live verification."]
        row["revision_notes"] = ["Explicit selected park supplied by the test fixture; do not ask the visitor to select it again."]
        row["family_id"] = f"product-{park}-{original['item_id']}"
        if row["expected_action"] == "answer":
            row["behavior_requirements"].append("Ground every factual claim in saved evidence from the selected park.")
        else:
            row["original_required_facts"] = row["required_facts"]
            row["required_facts"] = []
            row["revision_notes"].append("Score the unavailable fact or missing detail semantically; do not require the old refusal wording.")
            row["behavior_requirements"].append("Handle the requested unavailable fact or missing detail as described in expected_answer; do not invent it.")
        return row

    cases = [candidate(o, f"PG{i:03}", park) for i, (o, park) in enumerate(zip(originals, PARK_ASSIGNMENTS), 1)]
    for row in cases:
        row["history"] = []
    by_id = {r["item_id"]: r for r in cases}

    by_id["PG010"]["required_facts"] = ["The rotating globe illustrates volcanic hotspots around the world."]
    by_id["PG010"]["revision_notes"].append("The globe's weight is not required to answer what it illustrates.")
    by_id["PG011"]["required_facts"] = ["Cedar Ridge is 1.5 miles (2.4 km) from the South Kaibab rim trailhead.", "The DW column is blank; drinking water is not marked in that table."]
    by_id["PG011"]["forbidden_contradictions"].append("A blank DW cell proves a verified current absence of water.")
    header = evidence("grca", "trail-distances", "| Distance Via: | Distance from Rim (mi/km) | Elevation (ft/m) | DW | TF | EP | RS | Other |")
    south_kaibab = evidence("grca", "trail-distances", "| South Kaibab Trailhead to: |  | 7260/2213 |  |  |  |  |  |")
    by_id["PG011"]["evidence"] += [header, south_kaibab]
    by_id["PG011"]["revision_notes"].append("Corrected the old rubric's categorical 'no drinking water' to the actual blank table cell; added column headers.")
    # Preserve complete support for qualifications inherited from the original
    # reference prose, not just its main fact. These are exact saved-source spans.
    for identifier, park, page, quotes in [
        ("PG016", "yose", "internet", ["Tuolumne Meadows: No cell service."]),
        ("PG017", "yose", "campingfaq", ["All vehicles must be parked on a parking pad."]),
        ("PG018", "yell", "parkroads", ["The only road generally open year-round to regular vehicles is"]),
        ("PG021", "grca", "hike-smart", ["only the Bright Angel and North Kaibab Trails have potable water spigots"]),
        ("PG021", "grca", "safe-water", ["standard backpacking water filters are designed to remove bacteria, protozoa, and sediment, but"]),
        ("PG035", "grca", "hike-smart", ["we strongly recommend consulting with your physician before attempting rigorous hikes, especially in hot weather."]),
    ]:
        by_id[identifier]["evidence"] += [evidence(park, page, q) for q in quotes]
        by_id[identifier]["revision_notes"].append("Added exact evidence for reference qualifications or safe referral.")

    replacements = {
        "PG022": {
            "question": "In Yellowstone, how do the minimum viewing distances for bears and bison compare?",
            "expected_answer": "Stay at least 100 yards (91 m) from bears and at least 25 yards (23 m) from bison. Both are minimum separation rules.",
            "required_facts": ["Bears: at least 100 yards (91 m).", "Bison: at least 25 yards (23 m)."],
            "forbidden_contradictions": ["Twenty-five yards is sufficient for a bear.", "These are maximum distances."],
            "evidence": deepcopy(originals[7]["evidence"]),
        },
        "PG023": {
            "question": "At a Yosemite campground, how do quiet hours differ from the permitted generator hours?",
            "expected_answer": "Quiet hours are 10 pm–6 am. Generator use is allowed only 7–9 am, noon–2 pm, and 5–7 pm; being outside quiet hours does not itself permit generator use.",
            "required_facts": ["Quiet hours: 10 pm to 6 am.", "Generators: only 7–9 am, noon–2 pm, and 5–7 pm."],
            "forbidden_contradictions": ["Generators may operate whenever quiet hours are over."],
            "evidence": [evidence("yose", "campregs", q) for q in ["Quiet hours are from 10 pm to 6 am.", "Generator use is allowed only from 7 am to 9 am, noon to 2 pm, and 5 pm to 7 pm."]],
        },
        "PG024": {
            "question": "On Grand Canyon park shuttle buses, how does access differ for an ordinary pet dog and a dog individually trained to perform disability-related tasks?",
            "expected_answer": "Ordinary pets are prohibited. Service dogs as defined by the ADA are permitted; an individually trained dog must perform work or tasks related to its handler's disability. Comfort alone does not qualify.",
            "required_facts": ["Ordinary pets are prohibited on the shuttle.", "ADA-defined service dogs are permitted.", "Service-dog work or tasks must be individually trained and related to the handler's disability; comfort alone does not qualify."],
            "forbidden_contradictions": ["Ordinary pets become service dogs merely by providing comfort."],
            "evidence": [evidence("grca", "shuttle-buses", q) for q in ["No pets allowed on shuttle buses. Service dogs are permitted (as defined by the Americans With Disabilities Act ).", "any dog that is individually trained to do work or perform tasks for the benefit of an individual with a disability", "The work or tasks performed by a service animal must be directly related to the handler's disability.", "emotional support, well-being, comfort, or companionship do not constitute work or tasks for the purposes of this definition."]],
        },
        "PG025": {
            "question": "In Yosemite, can an ordinary leashed pet use the paved road to Mirror Lake and the unpaved trail around it? Is Wawona Meadow Loop a named exception to the general trail restriction?",
            "expected_answer": "The paved road to Mirror Lake is allowed unless signed otherwise; the unpaved trail around it is not. Wawona Meadow Loop is a named exception where pets are allowed. The leash may be no more than six feet long.",
            "required_facts": ["Mirror Lake paved road permitted, subject to posted restrictions.", "Mirror Lake unpaved loop not permitted.", "Wawona Meadow Loop is a named permitted trail exception.", "Leash no more than six feet long."],
            "forbidden_contradictions": ["All Yosemite trails are pet-friendly.", "No Yosemite trail has any pet exception."],
            "evidence": [evidence("yose", "pets", q) for q in ["On fully paved roads, sidewalks, and bicycle paths (except when signed as not allowing pets)", "the paved road to Mirror Lake (but not the unpaved trail around Mirror Lake).", "pets are allowed on the Wawona Meadow Loop", "pets must be restrained on a leash not more than six feet long or otherwise physically restrained"]],
        },
    }
    for identifier, changes in replacements.items():
        by_id[identifier].update(changes)
        by_id[identifier]["revision_notes"].append("Replaced an unsupported two-park answer with a comparison wholly inside one selected park.")

    by_id["PG030"]["question"] = "How many reservable Upper Pines campsites in Yosemite are vacant tonight, right now?"
    by_id["PG027"]["evidence"] = [unit for unit in by_id["PG027"]["evidence"] if "11 a.m." not in unit["quote"]]
    by_id["PG027"]["evidence"].append(evidence("yell", "operating-dates", "Facilities close at the end of the last business day listed, except campgrounds, which close at 11 a.m. on that day."))
    by_id["PG030"]["revision_notes"].append("Removed a hard-coded past date contradicting 'tonight'; live inventory remains unavailable.")
    by_id["PG038"]["expected_answer"] = "Ask which entrance, road, facility, trail or other place in Yosemite the visitor means. Ask for a date if needed; do not ask which park or assert a status."
    by_id["PG038"]["behavior_requirements"] += ["Clarify the missing place or facility; date is optional until its relevance is established.", "Do not treat the already selected park as unknown."]
    by_id["PG039"]["expected_answer"] = "Ask which pass type the visitor means for Yosemite, and any eligibility details needed to identify its fee. Do not ask which park or guess a price."
    by_id["PG039"]["behavior_requirements"] += ["Clarify the pass type and relevant eligibility.", "Do not treat the already selected park as unknown or invent a fee."]
    by_id["PG040"]["evidence"].append(evidence("grca", "shuttle-buses", "any dog that is individually trained to do work or perform tasks for the benefit of an individual with a disability"))

    refusal_requirements = {
        "PG030": "Refuse to report a live vacancy count; do not invent an inventory number.",
        "PG031": "Refuse to provide an exact airline fare absent from the park corpus; do not invent a price.",
        "PG032": "Explain lack of private booking access; do not invent an assigned campsite or imply the booking was checked.",
        "PG033": "Refuse the exact forecast; do not convert general climate into an exact temperature.",
        "PG034": "Refuse a guaranteed wildlife probability; do not invent a percentage.",
        "PG035": "Refuse personal medical clearance and refer the visitor to a qualified clinician; general park safety is not individual clearance.",
        "PG036": "Refuse a live entrance queue measurement; do not invent minutes.",
        "PG037": "Refuse an exact future volcano-eruption date; geyser predictions are not volcano predictions.",
    }
    for identifier, requirement in refusal_requirements.items():
        by_id[identifier]["behavior_requirements"].append(requirement)
    for identifiers, family in [(["PG001", "PG023"], "yose-campground-generator-hours"), (["PG003", "PG025"], "yose-pet-trail-rules"), (["PG008", "PG022"], "yell-wildlife-distances"), (["PG024", "PG040"], "grca-shuttle-pet-service-dog")]:
        for identifier in identifiers:
            by_id[identifier]["family_id"] = "product-" + family

    # Out-of-scope prompts test the refusal boundary, never cross-park knowledge.
    controls = []
    for index, original in enumerate(originals[21:25], 1):
        row = candidate(original, f"PSC{index:02}", "yose")
        row.update(category="scope_boundary", expected_action="refuse", history=[], evidence=[], required_facts=[],
                   expected_answer="Explain that this chat is for Yosemite and direct the visitor to the park selector; do not answer the other park or change this chat's scope.",
                   forbidden_contradictions=["Answering factual comparisons across parks in this chat."],
                   family_id=f"product-scope-boundary-{index}")
        row["behavior_requirements"] += ["Return selected_park_mismatch refusal before retrieval or generation.", "Do not change the selected park or carry this conversation into another park."]
        row["revision_notes"].append("Original two-park prompt retained only as a separate guard control; excluded from the knowledge suite.")
        controls.append(row)

    # Six conversations now preserve their park throughout all three turns.
    dialogue_path = ROOT / "data/evaluation/dialogues.jsonl"
    dialogues = deepcopy(load_lines(dialogue_path))
    dialogue_parks = ["yose", "grca", "yose", "yose", "grca", "yell"]
    for dialogue, park in zip(dialogues, dialogue_parks):
        dialogue["original_dialogue_id"] = dialogue["dialogue_id"]
        dialogue["dialogue_id"] = "P" + dialogue["dialogue_id"]
        dialogue.update(selected_park=park, benchmark_eligible=False, verification_status="human_review_pending")
        dialogue["history_mode"] = "Append actual completed user/assistant exchanges and actual assistant evidence_ids. Never insert reference answers. Keep this selected park for all turns."
        dialogue["turns"] = [candidate(t, "P" + t["item_id"], park) for t in dialogue["turns"]]
        for turn in dialogue["turns"]:
            turn["turn_id"] = turn["item_id"]
            turn.pop("history", None)
            turn["history_from"] = "actual preceding completed responses in this dialogue"
    dialogues[0]["scenario"] = "Change guide dates within Yosemite without retaining an obsolete period"
    turn = dialogues[0]["turns"][2]
    turn.update(question="For that October 2026 visit, would the old June 2025 Yosemite guide issue still apply? Give the period that does apply.",
                expected_answer="No. Volume 51, Issue 8 covers September 23–November 24, 2026; the earlier June 2025 issue does not cover that visit.",
                evidence=deepcopy(originals[25]["evidence"]), required_facts=deepcopy(originals[25]["required_facts"]),
                forbidden_contradictions=["Retaining the June 2025 issue for October 2026."])
    dialogues[1]["turns"][1].update(required_facts=["Cedar Ridge's DW column is blank; drinking water is not marked in the saved table."],
                                     expected_answer="The saved table does not mark drinking water at Cedar Ridge; its DW cell is blank. This is not a live availability check.")
    for turn in dialogues[1]["turns"]:
        turn["evidence"].append(deepcopy(header))
    dialogues[1]["turns"][0]["question"] = "According to Grand Canyon's saved South Kaibab table, what is the one-way trail distance from the rim trailhead to Cedar Ridge?"
    dialogues[1]["turns"][0]["evidence"].append(deepcopy(south_kaibab))
    dialogues[1]["turns"][0]["revision_notes"].append("Clarified along-trail distance; 'below the rim' could mean vertical elevation drop.")
    turn = dialogues[1]["turns"][2]
    turn["evidence"].append(deepcopy(south_kaibab))
    turn["required_facts"] = ["Cedar Ridge: 1.5 miles (2.4 km) one way from the rim trailhead.", "Skeleton Point: 3 miles (4.8 km) one way from the same trailhead.", "Skeleton Point is 1.5 miles (2.4 km) farther along the trail than Cedar Ridge."]
    turn["expected_answer"] = "Skeleton Point is 3 miles (4.8 km) from the rim trailhead versus Cedar Ridge's 1.5 miles (2.4 km), so it is 1.5 miles (2.4 km) farther along the trail."
    turn["calculation"] = {"operation": "subtract distances from the same trailhead", "miles": "3 - 1.5 = 1.5", "km": "4.8 - 2.4 = 2.4"}
    dialogues[2]["scenario"] = "Resolve a same-park bear follow-up and contrast developed versus undeveloped settings"
    developed = evidence("yose", "bears", "If you see a bear in a developed area or if a bear approaches you, scare it away by yelling very loudly and aggressively.")
    turn = dialogues[2]["turns"][1]
    turn.update(question="And if that bear is in a developed area or approaches me?", expected_answer="The saved Yosemite page says to scare it away by yelling very loudly and aggressively.",
                evidence=[developed], required_facts=["In a developed area or if approached by a bear, scare it away by yelling very loudly and aggressively."],
                forbidden_contradictions=["Approach or surround the bear."])
    turn = dialogues[2]["turns"][2]
    turn.update(question="Compare those two situations in Yosemite. Which instruction belongs to each?", expected_answer="Outside developed areas, remain at least 50 yards away. In a developed area or if approached by a bear, scare it away by yelling very loudly and aggressively.",
                evidence=deepcopy(dialogues[2]["turns"][0]["evidence"]) + [developed],
                required_facts=["Outside developed areas: remain at least 50 yards away.", "In a developed area or if approached: scare the bear away by yelling very loudly and aggressively."],
                forbidden_contradictions=["Importing another park's distance rule.", "Approaching the bear."])
    dialogues[3]["turns"][0].update(question="Is it open?", expected_answer="Ask which Yosemite entrance, road, facility or other place the visitor means; do not ask which park or assert unrestricted access.")
    dialogues[3]["turns"][0]["revision_notes"].append("Replaced general 'go in whenever' wording with an unmistakably missing referent; a general opening-rule answer to the old wording could be valid.")
    dialogues[3]["turns"][0]["behavior_requirements"] += ["Clarify the missing entrance or place, not the already selected park."]
    dialogues[3]["turns"][1]["evidence"].append(deepcopy(originals[3]["evidence"][0]))
    dialogues[4]["turns"][0]["behavior_requirements"] += ["Refuse private booking lookup; do not invent a campsite assignment."]
    dialogues[4]["turns"][2]["evidence"].append(deepcopy(dialogues[4]["turns"][1]["evidence"][1]))
    dialogues[5]["turns"][2]["behavior_requirements"] += ["Refuse personal medication dosage and clearance to keep hiking; advise qualified medical or urgent park assistance."]

    # Retain all diagnostics; their UI setup and clarification expectations change.
    diagnostic_path = ROOT / "data/evaluation/diagnostic.jsonl"
    diagnostics = [candidate(o, "P" + o["item_id"], park) for o, park in zip(load_lines(diagnostic_path), ["yose"]*3 + ["yell"]*2 + ["grca"]*5 + ["yose"]*2)]
    for row in diagnostics:
        row["history"] = []
    diagnostics[7]["evidence"].append(evidence("grca", "desert-view-drive", "and the East Entrance of Grand Canyon National Park."))
    diagnostics[9]["evidence"].append(evidence("grca", "lost-found", "make a lost property report and send it to Grand Canyon National Park's Lost and Found Office."))
    diagnostics[10]["expected_answer"] = "Ask what item or animal the visitor means in Yosemite, and the relevant place or activity. The selected park is already known."
    diagnostics[10]["behavior_requirements"].append("Clarify the missing item/place without asking which park.")
    diagnostics[11]["expected_answer"] = "Ask for the visitor's starting location or reference point in Yosemite before identifying the closest campground. The selected park is already known."
    diagnostics[11]["behavior_requirements"].append("Ask for a starting location; do not invent the visitor's location or ask which park.")

    OUT.mkdir(parents=True, exist_ok=args.refresh_draft)
    for filename, rows in [("gold-candidates.jsonl", cases), ("scope-controls.jsonl", controls), ("dialogue-candidates.jsonl", dialogues), ("diagnostic-candidates.jsonl", diagnostics)]:
        save_lines(OUT / filename, rows)
    manifest = {"created_at": created, "status": "HUMAN_REVIEW_PENDING", "benchmark_eligible": False,
                "purpose": "Product-aligned revision proposals and separate operational scope controls; not final gold or measured chatbot accuracy.",
                "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "builder_sha256": sha(Path(__file__)),
                "contract_file_hashes": {str(p.relative_to(ROOT)): sha(p) for p in [ROOT / "src/parkguide/chat.py", ROOT / "src/parkguide/web.py", ROOT / "src/parkguide/evaluation.py", ROOT / "web/src/App.tsx", ROOT / "web/src/lib/chat-storage.ts"]},
                "original_gold_sha256": ORIGINAL_SHA, "database_sha256": DB_SHA,
                "input_hashes": {str(p.relative_to(ROOT)): sha(p) for p in [original_path, dialogue_path, diagnostic_path]},
                "output_hashes": {p.name: sha(p) for p in sorted(OUT.glob("*.jsonl"))},
                "counts": {"knowledge_candidates": 40, "scope_controls": 4, "dialogues": 6, "dialogue_turns": 18, "diagnostics": 12},
                "execution_contract": "Use POST /api/chat with selected_park/question/history, or answer(question, history, selected_park=...). Legacy evaluation.run omits selected_park and is incompatible. Changing the UI park starts a separate chat with empty history.",
                "review_contract": "All labels are AI proposals. Preserve source evidence and behavioral quality requirements. Human review and grouped split must precede any formal benchmark.",
                "split_contract": "Group repeated evidence/topic families; no dev/test split created. This 40-item revision alone still lacks PDF and persistence/UI coverage.",
                "paid_calls": 0, "chatbot_outputs_generated": 0}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    assert sha(original_path) == ORIGINAL_SHA and sha(db_path) == DB_SHA
    conn.close()
    print(json.dumps({"out": str(OUT.relative_to(ROOT)), "counts": manifest["counts"], "paid_calls": 0}))


if __name__ == "__main__":
    main()
