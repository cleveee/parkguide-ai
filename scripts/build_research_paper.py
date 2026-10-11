"""Update the paper with Robin's contribution and the saved, checked evaluation.

The original manuscript remains in reports/research-paper/source/. Check mode
uses the installed project's offline evaluator; only write needs python-docx.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "reports/research-paper"
SOURCE = PAPER / "source/ParkGuide_AI_Research_Paper.docx"
OUTPUT = PAPER / "ParkGuide_AI_Research_Paper.docx"
MANIFEST = PAPER / "revision-manifest.json"
FIGURES = ROOT / "reports/figures/gold-matrix-v1"
RUN = ROOT / "artifacts/gold-matrix-v1"
ORIGINAL_SHA256 = "946a6b88243e4253e7ded4eb3a40de1c42d5a9a6cad29c426bea469ec9afc624"
ROBIN_CONTRIBUTION = (
    "Built the RAG pipeline, integrated Azure models and SQLite, and developed the "
    "React/FastAPI web app. Added park selection, source previews, and retrieval "
    "inspectors. Improved citation safeguards and conversation reliability, "
    "deployed the application on Vercel, and supported testing and technical documentation."
)


def read(path):
    return json.loads(path.read_text())


def digest(path, *, aggregate=False):
    content = path.read_bytes()
    if aggregate:
        value = json.loads(content)
        value.pop("created_at", None)
        content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(content).hexdigest()


def source_hashes():
    paths = [SOURCE, Path(__file__).resolve(), FIGURES / "figure-manifest.json",
             RUN / "chatbot/metadata.json", RUN / "metrics.json", RUN / "semantic-summary.json"]
    return {str(p.relative_to(ROOT)): {
        "sha256": digest(p, aggregate=p.name in {"metrics.json", "semantic-summary.json"}),
        "hash_mode": "canonical_json_without_created_at" if p.name in {"metrics.json", "semantic-summary.json"} else "bytes",
    } for p in paths}


def validate_inputs():
    if digest(SOURCE) != ORIGINAL_SHA256:
        raise ValueError("The supplied original manuscript has changed")
    for script in ("evaluate.py", "build_gold_matrix_figures.py"):
        # A separate document runtime can validate with the app's environment.
        python = os.environ.get("PARKGUIDE_EVAL_PYTHON", sys.executable) if script == "evaluate.py" else sys.executable
        result = subprocess.run([python, str(ROOT / "scripts" / script), "--check"],
                                cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f"{script} failed its offline check: {result.stderr.strip() or result.stdout.strip()}")


def check():
    validate_inputs()
    manifest = read(MANIFEST)
    if manifest["inputs"] != source_hashes() or manifest["output_sha256"] != digest(OUTPUT):
        raise ValueError("Research paper or its inputs changed; review and rebuild the paper")
    return {"status": "pass", "provider_calls": 0, "human_review": "pending"}


def write():
    validate_inputs()
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    metrics, semantic = read(RUN / "metrics.json"), read(RUN / "semantic-summary.json")
    metadata = read(RUN / "chatbot/metadata.json")
    action, retrieval, operational = (metrics[k] for k in ("action_metrics", "retrieval_metrics", "operational"))
    expected = {row["class"]: row for row in action["per_class"]}
    total, correct = action["n"], sum(row["tp"] for row in action["per_class"])
    passes = semantic["full_rubric_pass"]["passed"]
    answers = expected["answer"]["tp"] + expected["answer"]["fp"]
    run_date, commit = metadata["started_at"][:10], metadata["code_commit"][:7]
    fmt = lambda value: f"{100 * value:.1f}%"
    count = lambda n, d: f"{n}/{d} ({fmt(n/d)})"
    doc = Document(SOURCE)
    robin_rows = [row for row in doc.tables[0].rows
                  if row.cells[0].text.strip() == "Robin Cleve"]
    if len(robin_rows) != 1:
        raise ValueError("Expected exactly one Robin Cleve contribution row")
    contribution = robin_rows[0].cells[1].paragraphs[0]
    contribution.clear()
    for highlight in contribution._p.findall(".//" + qn("w:highlight")):
        highlight.getparent().remove(highlight)
    contribution.add_run("Engineer: ").bold = True
    contribution.add_run(ROBIN_CONTRIBUTION).bold = False
    for run in contribution.runs:
        run.font.name, run.font.size, run.font.color.rgb = "Times New Roman", Pt(8), RGBColor(0, 0, 0)
    baseline = deepcopy(doc.tables[1]._element)
    # The supplied baseline table is historical evidence; retain every value.
    for highlight in baseline.findall(".//" + qn("w:highlight")):
        highlight.getparent().remove(highlight)
    for node in baseline.findall(".//" + qn("w:t")):
        if node.text == "B3 (this run)":
            node.text = "B3 (earlier run)"
    section = next(p._element for p in doc.paragraphs if p.text.strip() == "7. Evaluation")
    body, started = doc._element.body, False
    for element in list(body):
        if element is section:
            started = True
        if started and element.tag != qn("w:sectPr"):
            body.remove(element)

    def paragraph(text="", *, bold_lead=None, size=10, after=5, keep=False):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(after)
        p.paragraph_format.line_spacing = 1.04
        p.paragraph_format.keep_with_next = keep
        p.paragraph_format.widow_control = True
        if bold_lead:
            p.add_run(bold_lead + " ").bold = True
        p.add_run(text)
        for run in p.runs:
            run.font.name, run.font.size, run.font.color.rgb = "Times New Roman", Pt(size), RGBColor(0, 0, 0)
        return p

    def heading(text, *, page=False):
        p = paragraph(text, size=10.5, after=5, keep=True)
        p.runs[0].bold = True
        p.paragraph_format.space_before = Pt(7)
        p.paragraph_format.page_break_before = page
        return p

    def caption(text):
        p = paragraph(text, size=8.5, after=7)
        for run in p.runs:
            run.italic = True
        return p

    def table(headers, rows, widths):
        result = doc.add_table(rows=1, cols=len(headers))
        result.style, result.alignment, result.autofit = "Table Grid", WD_TABLE_ALIGNMENT.CENTER, False
        for col, width in zip(result.columns, widths):
            col.width = Inches(width)
        for values in [headers, *rows]:
            cells = result.rows[0].cells if values is headers else result.add_row().cells
            for i, (cell, value) in enumerate(zip(cells, values)):
                cell.width, cell.vertical_alignment = Inches(widths[i]), WD_CELL_VERTICAL_ALIGNMENT.CENTER
                cell.text = str(value)
                p = cell.paragraphs[0]
                p.paragraph_format.space_after, p.paragraph_format.space_before = Pt(3), Pt(3)
                p.paragraph_format.line_spacing = 1
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if i == 0 else WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.name, run.font.size = "Times New Roman", Pt(9)
                    run.font.color.rgb = RGBColor(0, 0, 0)
                    run.bold = values is headers
                if values is headers:
                    shading = OxmlElement("w:shd")
                    shading.set(qn("w:fill"), "E8EEEE")
                    cell._tc.get_or_add_tcPr().append(shading)
        header = OxmlElement("w:tblHeader")
        result.rows[0]._tr.get_or_add_trPr().append(header)
        for row in result.rows:
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        # Keep the table's final row with its caption without chaining the entire table.
        for cell in result.rows[-1].cells:
            cell.paragraphs[-1].paragraph_format.keep_with_next = True
        return result

    def figure(name, text, *, width=6.6):
        p = paragraph(after=2, keep=True)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        picture = p.add_run().add_picture(str(FIGURES / name), width=Inches(width))
        picture._inline.docPr.set("descr", text)
        caption(text)

    def link(label, url):
        p = paragraph(after=4, size=9)
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), p.part.relate_to(url,
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True))
        run, props, text = OxmlElement("w:r"), OxmlElement("w:rPr"), OxmlElement("w:t")
        color = OxmlElement("w:color"); color.set(qn("w:val"), "245957"); props.append(color)
        size = OxmlElement("w:sz"); size.set(qn("w:val"), "18"); props.append(size)
        text.text = label; run.append(props); run.append(text); hyperlink.append(run); p._p.append(hyperlink)

    heading("7. Evaluation")
    paragraph("The repository contains two distinct evaluation tracks. The original course gold drafts were sealed before initial live answers, with a planned human-reviewed 24/16 development/test split (seed 633). That reviewed split and final-test benchmark remain pending. The later gold-matrix-v1 study uses revised, product-aligned candidates after development exposure; it does not inherit the original drafts' pre-output or held-out status.", bold_lead="Design.")
    paragraph("Table 1 preserves the earlier controlled comparison on 12 diagnostic items (8 with source evidence), using GPT-4.1 mini rather than the later Luna configuration. B0 is closed book; B1 and B2 use fixed chunks; C1, C2, and B3 are structure-aware retrieval ablations. Its paired intervals use 10,000 bootstrap resamples (seed 633).", bold_lead="Earlier retrieval experiment.")
    body.insert(len(body) - 1, baseline)
    caption("Table 1. Earlier controlled retrieval comparison. Paired MRR changes: B1 to B2 -0.325 [-0.563, -0.100]; B2 to C1 +0.304 [+0.083, +0.513]; C2 to B3 -0.073 [-0.219, +0.042]. Top-5 evidence coverage was 8/8 for every retrieval variant.")
    paragraph("Structure-aware chunking improved dense MRR by 0.304 in this exploratory comparison. Reranking showed no established gain and added 340 ms mean latency (95% paired interval 305 to 365 ms). These eight evidence-bearing items do not establish a general advantage, and this earlier baseline comparison is separate from the 40-question study below.")

    heading("7.1 Saved gold matrix outcomes", page=True)
    paragraph(f"On {run_date}, local chat.answer at commit {commit} completed {operational['completed']}/{operational['attempted']} requests with {operational['errors']} execution errors. Each request selected one park and began with empty history. The run used hybrid retrieval, no reranker, and Azure Luna (gpt-6-luna-2026-09-22), including generation and claim checks. Settings match the hosted profile; execution and latency were local, without Vercel/API/browser measurement.", bold_lead="Protocol.")
    paragraph("Five independent AI labeling configurations produced the 75-fact consensus reference for 40 questions. Candidate-category lineage is 15 factual, 6 multi-hop, 4 comparative, 4 temporal, 8 unanswerable, and 3 ambiguous/adversarial; five of the six multi-hop references use multiple pages, while PG016 resolves from one. A separate gpt-5.6-sol/high assessor graded the saved responses. Human verification and assessor calibration remain pending. No new chatbot or grading calls were made for this report revision.")
    table(["Measurement", "Saved result", "Unit"], [
        ["Correct action", count(correct, total), "Questions"],
        ["Full rubric pass, AI assessed", count(passes, total), "Questions"],
        ["Required facts delivered, AI assessed", count(semantic['facts']['covered'], semantic['fact_total']), "Required facts"],
        ["Behavior requirements satisfied, AI assessed", count(semantic['behaviors']['satisfied'], semantic['behavior_total']), "Requirements"],
        ["Delivered claims supported, AI assessed", count(semantic['delivered_claims']['supported'], semantic['claim_total']), f"Claims in {answers} answers"],
        ["Delivered claims with valid citation identity", count(semantic['claim_citation_identity_valid']['valid'], semantic['claim_total']), "Delivered claims"],
        ["MRR / nDCG at 10", f"{retrieval['mrr']['mean']:.3f} / {retrieval['ndcg_at_10']['mean']:.3f}", f"{retrieval['mrr']['denominator']} answerable cases"],
        ["Recorded latency p50 / p95", f"{operational['latency_p50_ms']/1000:.2f} s / {operational['latency_p95_ms']/1000:.2f} s", "40 local requests"],
    ], [3.55, 1.65, 1.8])
    caption("Table 2. Saved local end-to-end backend RAG evaluation. A full pass requires the correct action, all required facts and behaviors, supported delivered claims, and no additional answer issue; uncertain judgments do not pass.")
    figure("outcomes.png", "Figure 2. High action agreement and cited-claim support coexist with incomplete answers. Denominators differ by metric and are printed beside each bar. All semantic results are provisional AI assessments.")
    paragraph("These descriptive rates are not population accuracy estimates. Facts and claims cluster within questions, sources overlap, and the questions have prior development exposure. Independent-observation confidence intervals would omit those dependencies and uncertainty in both the reference and assessor.")

    heading("7.2 Evidence coverage and delivered information", page=True)
    paragraph("Evidence coverage asks whether retrieved source spans cover a declared evidence group for a required fact. Delivered-fact coverage asks whether the answer conveys that fact according to the AI assessor. Figure 3 uses the same 75-fact denominator for each rate, while preserving the distinction between these measurements.")
    figure("evidence-and-answer.png", "Figure 3. Separate pooled measurements of declared evidence and delivered facts. These bars are not a nested funnel and their differences do not measure causal losses at successive stages.")
    table(["Evidence measure", "Pooled facts", "Mean per question"], [
        ["Top 5 ranked candidates", count(retrieval['at_5']['facts_covered'], retrieval['at_5']['facts_total']), fmt(retrieval['at_5']['fact_evidence_coverage'])],
        ["Top 20 ranked candidates", count(retrieval['at_20']['facts_covered'], retrieval['at_20']['facts_total']), fmt(retrieval['at_20']['fact_evidence_coverage'])],
        ["Actual generation contexts", count(retrieval['generation_context_fact_evidence_coverage']['facts_covered'], retrieval['generation_context_fact_evidence_coverage']['facts_total']), fmt(retrieval['generation_context_fact_evidence_coverage']['mean'])],
    ], [3.4, 1.8, 1.8])
    caption("Table 3. Pooled rates count 75 required facts; per-question means give equal weight to each of the 30 answerable cases. Top-k ranks precede context pruning. The two aggregations answer different questions.")
    paragraph("Four facts judged delivered lack complete declared evidence-group coverage in the actual contexts: M008 F1, M010 F1/F2, and M034 F1. Declared alternatives are not exhaustive human relevance judgments, so this mismatch alone does not demonstrate unsupported content. A per-fact review of source spans and semantic labels is needed before attributing errors to context selection or generation.", bold_lead="Interpretation.")
    r5, r20 = retrieval['at_5'], retrieval['at_20']
    paragraph(f"At rank 5, {r5['tp']}/{r5['retrieved']} returned chunks match declared relevance and {r5['tp']}/{r5['known_relevant']} known relevant chunks are recovered: micro precision {fmt(r5['micro_precision'])}, recall {fmt(r5['micro_recall'])}, F1 {fmt(r5['micro_f1'])}. At rank 20 the corresponding counts are {r20['tp']}/{r20['retrieved']} and {r20['tp']}/{r20['known_relevant']}, yielding {fmt(r20['micro_precision'])}, {fmt(r20['micro_recall'])}, and {fmt(r20['micro_f1'])}. These chunk metrics differ from required-fact coverage; the same fact can have several supporting chunks.", bold_lead="Chunk retrieval.")

    heading("7.3 Action errors and incomplete responses", page=True)
    figure("action-confusion.png", "Figure 4. Expected versus observed actions for all 40 questions. The three disagreements are over-refusals of answerable questions. This action classification does not measure all requirements of the response.", width=4.7)
    paragraph(f"Answer recall is {fmt(expected['answer']['recall'])}; refusal precision is {fmt(expected['refuse']['precision'])}. All eight expected refusals and both expected clarifications received their expected action. Full rubric compliance is lower because missing facts, referrals, clarifying behavior, and caveats also matter. Action micro precision, recall, and F1 are each {fmt(action['micro_f1'])}; macro F1 is {fmt(action['macro_f1'])}.")
    groups = [
        ("Missing required facts", ["M004", "M005", "M012", "M014", "M025", "M034", "M037", "M039"]),
        ("Over-refusal", ["M024", "M027", "M036"]),
        ("Missing or misdirected referral", ["M011", "M020", "M029"]),
        ("Missing clarifying behavior", ["M007", "M026"]),
        ("Missing snapshot caveat", ["M010", "M013"]),
        ("Inadequate source-limit explanation", ["M031"]),
    ]
    grouped = [item for _, ids in groups for item in ids]
    if len(grouped) != len(set(grouped)) or set(grouped) != set(semantic['not_full_pass_item_ids']):
        raise ValueError("Paper failure groups no longer match the saved assessment")
    table(["Primary issue", "Cases", "Case IDs"], [[name, len(ids), ", ".join(ids)] for name, ids in groups], [2.5, .55, 3.95])
    caption(f"Table 4. The {len(grouped)} unsuccessful cases, grouped once each by their principal recorded issue. Case-level reasons and all 40 responses remain available in the linked artifacts.")
    paragraph("M036 triggered number_without_source_witness, so its missing answer includes a numeric-guard refusal. M026 and M034 have uncertain semantic labels, which remain failures under the scoring rule. No unsuccessful case was removed, relabeled, or retried for this revision.")
    heading("8. Future Work")
    paragraph("Human-review the original course reference labels, freeze the planned 24/16 development/test split, and run the B0-B3 final comparison once under its evaluation gates. Separately, review the product-aligned matrix and calibrate its AI assessor against human grades. Use development cases to improve completeness and reduce over-refusal, then evaluate the hosted API/browser path and multi-turn conversations. Verify table/PDF extraction and replace the placeholder crawler contact. None of these pending measurements is established by offline replay.")
    paragraph("The repository preserves the original paper, saved responses, exact metric counts, and reproducible PNG/SVG charts. Run scripts/evaluate.py --check to reproduce scores without provider calls; the figures and manuscript have separate offline check commands documented in the evaluation workflow.", bold_lead="Reproducibility.")
    base = "https://github.com/cleveee/parkguide-ai/blob/main/"
    link("Evaluation report and methods", base + "reports/GOLD_MATRIX_EVALUATION.md")
    link("All 40 question results and recorded failures", base + "reports/GOLD_MATRIX_RESULTS.md")
    link("Figure data, source hashes, and reproduction workflow", base + "reports/figures/gold-matrix-v1/README.md")

    # Retain the supplied content outside the revised sections. Normalize the
    # title and heading color while keeping their existing size and alignment.
    title = doc.paragraphs[0]
    title.style = doc.styles["Title"]
    title.style.font.color.rgb = RGBColor(0, 0, 0)
    for border in title.style.element.findall(".//" + qn("w:pBdr")):
        border.getparent().remove(border)
    title.paragraph_format.space_after = Pt(3)
    for run in title.runs:
        run.font.name, run.font.size, run.font.color.rgb = "Times New Roman", Pt(13), RGBColor(0, 0, 0)
    for p in doc.paragraphs:
        if p.text[:3] in {f"{number}. " for number in range(1, 9)}:
            for run in p.runs:
                run.font.color.rgb = RGBColor(0, 0, 0)
    doc.save(OUTPUT)
    manifest = {"status": "AI_PROVISIONAL_HUMAN_REVIEW_PENDING", "provider_calls": 0,
                "source_run_date": run_date, "source_code_commit": metadata['code_commit'],
                "revised_sections": ["Author contributions (Robin Cleve)", "7 Evaluation", "8 Future Work"],
                "original_sha256": ORIGINAL_SHA256, "inputs": source_hashes(),
                "output_sha256": digest(OUTPUT)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"status": "written", "provider_calls": 0, "human_review": "pending", "output": str(OUTPUT)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true", help="check saved paper and inputs (default)")
    args = parser.parse_args()
    try:
        result = write() if args.write else check()
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Research paper validation failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
