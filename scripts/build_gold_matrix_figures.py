"""Build or verify publication figures for the saved gold-matrix-v1 diagnostic.

Data preparation and --check use only the Python standard library. Rendering
with --write additionally needs Matplotlib (the saved figures use 3.10.8).
No provider calls or new semantic judgments are made.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True

from assess_gold_matrix import summarize_assessments
from evaluation_integrity import read_json, require, unique_rows, validate_frozen_inputs
from gold_matrix import DATA, ROOT, RUN, readlines, sha

OUTPUT = ROOT / "reports/figures/gold-matrix-v1"
FIGURES = ("outcomes", "evidence-and-answer", "action-confusion")
ACTIONS = ("answer", "refuse", "clarify")


def serialized(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def canonical_hash(value):
    return hashlib.sha256(serialized(value).encode()).hexdigest()


def source_covered(unit, chunks):
    """Union matching source intervals, using the saved scorer's half-open rule."""
    intervals = []
    for chunk in chunks:
        if chunk["doc_id"] != unit["doc_id"] or chunk["content_hash"] != unit["content_hash"]:
            continue
        spans = chunk.get("source_span", chunk.get("source_span_json", []))
        if isinstance(spans, str):
            spans = json.loads(spans)
        if isinstance(spans, dict):
            spans = spans.get("spans", [spans])
        intervals.extend((span["start"], span["end"]) for span in spans
                         if span["end"] > unit["start"] and span["start"] < unit["end"])
    cursor = unit["start"]
    for start, end in sorted(intervals):
        if start > cursor:
            break
        cursor = max(cursor, end)
    return cursor >= unit["end"]


def fact_covered(fact, chunks):
    return any(all(source_covered(unit, chunks) for unit in group) for group in fact["evidence_groups"])


def measurement(identifier, label, numerator, denominator, unit, assessment):
    require(denominator > 0 and 0 <= numerator <= denominator, f"Invalid count for {identifier}")
    return {"id": identifier, "label": label, "numerator": numerator, "denominator": denominator,
            "unit": unit, "percentage": 100 * numerator / denominator, "assessment": assessment}


def build_data():
    """Derive an auditable, timestamp-free figure specification from frozen inputs."""
    identities = validate_frozen_inputs()
    refs = unique_rows(readlines(DATA / "gold-consensus.jsonl"), "references", count=40)
    bots = unique_rows(readlines(RUN / "chatbot/responses.jsonl"), "responses", expected_ids=refs, count=40)
    judgments = read_json(RUN / "semantic-assessment.json")["assessments"]
    judged = unique_rows(judgments, "assessments", expected_ids=refs, count=40)
    semantic = summarize_assessments(read_json(RUN / "semantic-input.json"), judgments)
    saved_semantic = read_json(RUN / "semantic-summary.json")
    semantic_provenance = read_json(RUN / "semantic-provenance.json")
    assessor_count = semantic_provenance.get("assessor_count")
    require(type(assessor_count) is int and assessor_count == 1, "These figures require the saved single-assessor study")
    for key, value in semantic.items():
        if key != "created_at":
            require(saved_semantic.get(key) == value, f"Saved semantic summary is stale: {key}")
    metrics = read_json(RUN / "metrics.json")
    require(metrics.get("dataset_sha256") == identities["dataset_sha256"]
            and metrics.get("responses_sha256") == identities["responses_sha256"], "Saved metrics use different inputs")
    per_item = unique_rows(readlines(RUN / "per-item-metrics.jsonl"), "per-case metrics", expected_ids=refs, count=40)
    meta = read_json(RUN / "chatbot/metadata.json")
    predictions = {key: bot.get("result", {}).get("response", {}).get("action", "error") for key, bot in bots.items()}
    labels = list(ACTIONS) + (["error"] if "error" in predictions.values() else [])
    confusion = [[sum(refs[key]["action"] == expected and predictions[key] == observed for key in refs)
                  for observed in labels] for expected in ACTIONS]
    correct = sum(refs[key]["action"] == predictions[key] for key in refs)
    require(metrics["action_metrics"]["accuracy"] == correct / len(refs), "Saved action accuracy is stale")
    claims_per_answer = Counter()
    for bot in bots.values():
        response = bot.get("result", {}).get("response", {})
        if response.get("claims"):
            require(response.get("action") == "answer", "A non-answer unexpectedly contains delivered claims")
            claims_per_answer[len(response["claims"])] += 1
    claim_cases = sum(claims_per_answer.values())
    require(sum(n * cases for n, cases in claims_per_answer.items()) == semantic["claim_total"], "Claim denominator mismatch")
    outcomes = [
        measurement("action", "Correct action", correct, len(refs), "responses", "counted against AI-consensus action labels"),
        measurement("rubric", "Full rubric pass", semantic["full_rubric_pass"]["passed"], len(refs), "responses", "one AI semantic assessor"),
        measurement("facts", "Required facts delivered", semantic["facts"].get("covered", 0), semantic["fact_total"], "required facts", "one AI semantic assessor"),
        measurement("behavior", "Behavior requirements met", semantic["behaviors"].get("satisfied", 0), semantic["behavior_total"], "behavior requirements", "one AI semantic assessor"),
        measurement("claims", "Delivered claims supported", semantic["delivered_claims"].get("supported", 0), semantic["claim_total"], "delivered claims", "one AI semantic assessor"),
    ]
    totals = Counter()
    context_delivery = Counter()
    exceptions = []
    answerable_cases = 0
    for key, ref in refs.items():
        if ref["action"] != "answer" or not ref["required_facts"]:
            continue
        answerable_cases += 1
        result = bots[key].get("result", {})
        retrieval = result.get("retrieval", {})
        ranked = retrieval.get("reranked", []) or retrieval.get("candidates", [])
        contexts = result.get("contexts", [])
        statuses = {fact["fact_id"]: fact["status"] for fact in judged[key]["facts"]}
        counts = Counter()
        for fact in ref["required_facts"]:
            top5 = fact_covered(fact, ranked[:5])
            top20 = fact_covered(fact, ranked[:20])
            context = fact_covered(fact, contexts)
            delivered = statuses[fact["fact_id"]] == "covered"
            counts.update(total=1, top5=int(top5), top20=int(top20), context=int(context), delivered=int(delivered))
            context_delivery[f"context_{str(context).lower()}_delivered_{str(delivered).lower()}"] += 1
            if delivered and not context:
                exceptions.append({"item_id": key, "fact_id": fact["fact_id"]})
        for k in (5, 20):
            saved = per_item[key][f"retrieval_at_{k}"]
            require(saved["facts_covered"] == counts[f"top{k}"] and saved["facts_total"] == counts["total"],
                    f"{key}: saved top-{k} evidence count is stale")
        require(per_item[key]["generation_context_facts_covered"] == counts["context"]
                and per_item[key]["generation_context_facts_total"] == counts["total"], f"{key}: saved context coverage is stale")
        totals.update(counts)
    require(totals["total"] == semantic["fact_total"] and totals["delivered"] == semantic["facts"].get("covered", 0),
            "The pooled fact measurements have different denominators")
    evidence = [
        measurement("top20", "Declared evidence in top 20", totals["top20"], totals["total"], "required facts", "source-span coverage"),
        measurement("context", "Declared evidence in generation context", totals["context"], totals["total"], "required facts", "source-span coverage"),
        measurement("delivered", "Required facts delivered", totals["delivered"], totals["total"], "required facts", "one AI semantic assessor"),
    ]
    raw_paths = [DATA / "gold-consensus.jsonl", RUN / "chatbot/responses.jsonl", RUN / "chatbot/metadata.json",
                 RUN / "semantic-input.json", RUN / "semantic-assessment.json", RUN / "semantic-provenance.json",
                 RUN / "per-item-metrics.jsonl"]
    aggregates = {}
    for name in ("metrics.json", "semantic-summary.json"):
        value = read_json(RUN / name)
        value.pop("created_at", None)
        aggregates[str((RUN / name).relative_to(ROOT))] = canonical_hash(value)
    local_date = datetime.fromisoformat(meta["started_at"]).astimezone(ZoneInfo("America/Chicago")).date().isoformat()
    return {
        "schema_version": 1,
        "study": {"id": "gold-matrix-v1", "saved_run_date": local_date, "date_timezone": "America/Chicago",
                  "code_commit": meta["code_commit"], "model": meta["model"], "retrieval_mode": meta["mode"],
                  "rerank_enabled": meta["rerank_enabled"], "execution": meta["execution"], "cases": len(refs),
                  "answerable_cases": answerable_cases, "semantic_assessor_count": assessor_count, "human_verified": False,
                  "benchmark_eligible": False},
        "frozen_inputs": identities,
        "input_sha256": {str(path.relative_to(ROOT)): sha(path) for path in raw_paths},
        "aggregate_sha256_without_created_at": aggregates,
        "aggregate_hash_encoding": "UTF-8 JSON, sorted keys, two-space indentation, ensure_ascii=False, trailing newline; omit only top-level created_at",
        "outcomes": outcomes,
        "claim_denominator": {"delivered_claims": semantic["claim_total"], "answer_cases_with_claims": claim_cases,
                              "claims_per_answer_distribution": {str(n): count for n, count in sorted(claims_per_answer.items())}},
        "evidence_and_answer": evidence,
        "top5_declared_evidence": measurement("top5", "Declared evidence in top 5", totals["top5"], totals["total"], "required facts", "source-span coverage"),
        "context_delivery_alignment": dict(sorted(context_delivery.items())),
        "delivered_without_complete_declared_context_evidence": sorted(exceptions, key=lambda row: (row["item_id"], row["fact_id"])),
        "action_confusion": {"expected_labels": list(ACTIONS), "observed_labels": labels, "counts": confusion,
                             "expected_counts": [sum(row) for row in confusion], "correct": correct,
                             "total": len(refs), "over_refusals": confusion[0][labels.index("refuse")]},
        "limitations": [
            "Saved local run, not a new run or a measurement of the current Vercel deployment.",
            "AI-consensus references and one AI semantic assessor; human review pending.",
            "Development questions have prior exposure; this is not a held-out or human-verified benchmark.",
            "Outcome bars use different scoring units; supported delivered claims do not establish complete answers.",
            "Evidence coverage checks declared source-span groups, which are not exhaustive supporting alternatives; delivery is a separate semantic assessment.",
            "Evidence and delivery measurements are not nested sets and must not be interpreted as a causal funnel.",
            "Facts and claims cluster within responses, and some questions share topic families; no independent-binomial intervals are shown.",
        ],
    }


def render(data, destination):
    """Optional plotting dependency is imported only for an explicit --write."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.patches import Rectangle

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.hashsalt": "parkguide-gold-matrix-v1",
                         "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                         "axes.edgecolor": "#AEBBC0", "text.color": "#173743", "axes.labelcolor": "#173743",
                         "xtick.color": "#465D66", "ytick.color": "#173743", "svg.fonttype": "none"})
    navy, teal, amber = "#285F79", "#267A70", "#B96630"
    saved = f"Saved local run · {data['study']['saved_run_date']} · {data['study']['cases']} questions"
    caveat = "AI provisional · One AI semantic assessor · Human review pending"

    def save(fig, name):
        for extension in ("png", "svg"):
            metadata = ({"Software": "ParkGuide AI evaluation figures"} if extension == "png" else
                        {"Date": None, "Creator": "ParkGuide AI evaluation figures", "Title": name})
            fig.savefig(destination / f"{name}.{extension}", dpi=240, facecolor="white", metadata=metadata)
            if extension == "svg":
                path = destination / f"{name}.{extension}"
                path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
        plt.close(fig)

    def bars(name, title, subtitle, rows, labels, footnote, colors):
        fig = plt.figure(figsize=(8.4, 4.65))
        fig.text(0.025, 0.935, title, fontsize=16, weight="bold")
        fig.text(0.025, 0.875, saved, fontsize=10)
        fig.text(0.025, 0.823, subtitle, fontsize=9.5, color="#465D66")
        ax = fig.add_axes([0.335, 0.245, 0.465, 0.525])
        ys = list(range(len(rows)))
        ax.barh(ys, [row["percentage"] for row in rows], height=0.58, color=colors)
        ax.set_yticks(ys, labels)
        ax.tick_params(axis="y", length=0, pad=10, labelsize=10)
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
        ax.tick_params(axis="x", length=0, pad=7, labelsize=9)
        ax.invert_yaxis()
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#E1E7EA", linewidth=0.7)
        for y, row in zip(ys, rows):
            ax.text(1.025, y, f"{row['numerator']}/{row['denominator']}  ({row['percentage']:.1f}%)",
                    transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=10, weight="bold")
        fig.text(0.025, 0.13, footnote, fontsize=8.7, color="#465D66")
        fig.text(0.025, 0.06, caveat, fontsize=9, weight="bold")
        save(fig, name)

    bars("outcomes", "High citation support, lower answer completeness",
         "Exact counts are shown for each scoring unit; semantic grades remain provisional.",
         data["outcomes"], ["Correct action\nresponses", "Full rubric pass\nresponses", "Required facts delivered\nreference facts",
                            "Behavior requirements met\nrequirements", "Delivered claims supported\nclaims"],
         f"Claim support covers {data['claim_denominator']['delivered_claims']} delivered claims across "
         f"{data['claim_denominator']['answer_cases_with_claims']} answer cases; it does not measure answer completeness.",
         [navy, teal, teal, teal, teal])
    exception_count = len(data["delivered_without_complete_declared_context_evidence"])
    bars("evidence-and-answer", "Evidence coverage and delivered facts",
         f"Three distinct measurements against the same {data['evidence_and_answer'][0]['denominator']} reference facts; pooled counts.",
         data["evidence_and_answer"], ["Declared evidence\ntop 20 ranked chunks", "Declared evidence\nactual generation context",
                                     "Facts delivered\nAI semantic assessment"],
         f"{exception_count} delivered facts lack complete declared-context coverage. The measurements are not nested sets.",
         [navy, navy, teal])

    confusion = data["action_confusion"]
    fig = plt.figure(figsize=(7.2, 5.35))
    fig.text(0.03, 0.93, "Action decisions and over-refusals", fontsize=16, weight="bold")
    fig.text(0.03, 0.87, saved, fontsize=10)
    ax = fig.add_axes([0.28, 0.28, 0.59, 0.49])
    for y, row in enumerate(confusion["counts"]):
        for x, count in enumerate(row):
            matches = confusion["expected_labels"][y] == confusion["observed_labels"][x]
            color = teal if count and matches else amber if count else "#F0F4F5"
            ax.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, facecolor=color, edgecolor="white", linewidth=3))
            ax.text(x, y, str(count), ha="center", va="center", fontsize=23, weight="bold",
                    color="white" if count else "#83959D")
    ax.set_xlim(-0.5, len(confusion["observed_labels"]) - 0.5)
    ax.set_ylim(len(confusion["expected_labels"]) - 0.5, -0.5)
    ax.set_xticks(range(len(confusion["observed_labels"])), [label.title() for label in confusion["observed_labels"]])
    ax.set_yticks(range(len(confusion["expected_labels"])),
                  [f"{label.title()} (n={count})" for label, count in zip(confusion["expected_labels"], confusion["expected_counts"])])
    ax.tick_params(length=0, pad=8)
    ax.set_xlabel("Observed action", labelpad=11)
    ax.set_ylabel("Expected action", labelpad=10)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(0.03, 0.14, f"{confusion['correct']}/{confusion['total']} expected actions matched. "
             f"{confusion['over_refusals']}/{confusion['expected_counts'][0]} answerable questions received refusals.", fontsize=9.5)
    fig.text(0.03, 0.065, caveat, fontsize=9, weight="bold")
    save(fig, "action-confusion")
    return matplotlib.__version__


def check(output_dir=OUTPUT):
    output_dir = Path(output_dir)
    expected = build_data()
    require(read_json(output_dir / "chart-data.json") == expected, "Chart data is missing or stale; run --write")
    manifest = read_json(output_dir / "figure-manifest.json")
    require(manifest.get("generator_sha256") == sha(Path(__file__)), "Figure generator changed; run --write")
    require(manifest.get("chart_data_sha256") == sha(output_dir / "chart-data.json"), "Chart-data manifest hash is stale")
    files = ["chart-data.json"] + [f"{name}.{extension}" for name in FIGURES for extension in ("png", "svg")]
    require(set(manifest.get("files_sha256", {})) == set(files), "Figure manifest has missing or unexpected outputs")
    for name in files:
        require((output_dir / name).is_file() and sha(output_dir / name) == manifest["files_sha256"][name],
                f"Figure hash mismatch or missing file: {name}")
    return {"status": "verified", "figures": len(FIGURES), "files_checked": len(files), "output_dir": str(output_dir)}


def write(output_dir=OUTPUT):
    output_dir = Path(output_dir)
    data = build_data()
    with tempfile.TemporaryDirectory(prefix="parkguide-figures-") as temporary:
        stage = Path(temporary)
        version = render(data, stage)
        (stage / "chart-data.json").write_text(serialized(data))
        files = sorted(path.name for path in stage.iterdir() if path.is_file())
        manifest = {"schema_version": 1, "study": "gold-matrix-v1", "generator": "scripts/build_gold_matrix_figures.py",
                    "generator_sha256": sha(Path(__file__)), "matplotlib_version": version,
                    "chart_data_sha256": sha(stage / "chart-data.json"),
                    "files_sha256": {name: sha(stage / name) for name in files}}
        (stage / "figure-manifest.json").write_text(serialized(manifest))
        output_dir.mkdir(parents=True, exist_ok=True)
        for path in stage.iterdir():
            shutil.copyfile(path, output_dir / path.name)
    return check(output_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Verify saved data and figure hashes (default; standard library only)")
    mode.add_argument("--write", action="store_true", help="Render and save all figures (requires Matplotlib)")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        result = write(args.output_dir) if args.write else check(args.output_dir)
    except (ValueError, OSError, ImportError) as error:
        print(f"Figure verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
