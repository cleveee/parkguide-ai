"""Reproduce the saved evaluation offline; --write refreshes derived outputs.

No application requests, model calls, relabeling, or final-course-test execution.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile

from gold_matrix import ROOT, RUN, dump

ARTIFACTS = (
    "agreement.json",
    "metrics.json",
    "qrels.json",
    "per-item-metrics.jsonl",
    "semantic-summary.json",
    "dataset-audit.json",
    "result-manifest.json",
)
REPORTS = ("GOLD_MATRIX_EVALUATION.md", "GOLD_MATRIX_RESULTS.md")


def same_output(actual: Path, expected: Path) -> bool:
    if not expected.is_file():
        return False
    if actual.suffix == ".json":
        left = json.loads(actual.read_text())
        try:
            right = json.loads(expected.read_text())
        except ValueError:
            return False
        if not isinstance(right, dict):
            return False
        # Only top-level generation times are nondeterministic. Source times,
        # hashes, counts, and nested provenance remain part of the comparison.
        left.pop("created_at", None)
        right.pop("created_at", None)
        return left == right
    return actual.read_bytes() == expected.read_bytes()


def replay(*, write=False):
    from assess_gold_matrix import summarize
    from build_gold_matrix_report import main as build_report
    from derive_gold_matrix import score
    from evaluation_integrity import validate_frozen_inputs

    identity = validate_frozen_inputs()
    with tempfile.TemporaryDirectory(prefix="parkguide-eval-") as folder:
        artifacts, reports = Path(folder) / "artifacts", Path(folder) / "reports"
        artifacts.mkdir()
        with redirect_stdout(io.StringIO()):
            metrics = score(output_dir=artifacts)
            semantic = summarize(output_dir=artifacts)
            if not write:
                # Preserve saved generation timestamps for manifest byte hashes.
                # Every other field must still reproduce; no input is modified.
                for name in ARTIFACTS:
                    generated, saved = artifacts / name, RUN / name
                    if generated.is_file() and saved.is_file() and generated.suffix == ".json":
                        data = json.loads(generated.read_text())
                        try:
                            original = json.loads(saved.read_text())
                        except ValueError:
                            continue
                        if isinstance(original, dict) and "created_at" in data and "created_at" in original:
                            data["created_at"] = original["created_at"]
                            dump(generated, data)
            build_report(output_dir=artifacts, reports_dir=reports)
        if identity != validate_frozen_inputs():
            raise ValueError("Frozen evaluation inputs changed during replay")
        outputs = [(artifacts / name, RUN / name) for name in ARTIFACTS]
        outputs += [(reports / name, ROOT / "reports" / name) for name in REPORTS]
        changed = [str(target.relative_to(ROOT)) for source, target in outputs if not same_output(source, target)]
        if write:
            # Generate and validate the whole bundle before publishing any file.
            for source, target in outputs:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        return {
            "status": "written" if write else "pass" if not changed else "stale",
            "mode": "offline_saved_response_replay",
            "provider_calls": 0,
            "cases": metrics["action_metrics"]["n"],
            "correct_actions": sum(row["tp"] for row in metrics["action_metrics"]["per_class"]),
            "full_rubric_passes_ai": semantic["full_rubric_pass"]["passed"],
            "human_review": "pending",
            "derived_files": len(outputs),
            "changed_files": changed,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="regenerate derived results and reports after validation")
    mode.add_argument("--check", action="store_true", help="verify saved outputs without modifying files (default)")
    args = parser.parse_args()
    try:
        result = replay(write=args.write)
    except (ValueError, KeyError, OSError, AssertionError) as error:
        parser.exit(1, f"Evaluation validation failed: {error}\n")
    print(json.dumps(result, indent=2))
    if result["status"] == "stale":
        parser.exit(1, "Derived files are missing or stale. Review the changes, then run scripts/evaluate.py --write.\n")


if __name__ == "__main__":
    main()
