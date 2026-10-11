"""Exercise the complete saved-result workflow in an isolated repository copy."""
import json
from pathlib import Path
import shutil
import socket
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import assess_gold_matrix as assess
import build_gold_matrix_report as report
import derive_gold_matrix as derive
import evaluate
import evaluation_integrity as integrity


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    data = tmp_path / "data/evaluation/gold-matrix-v1"
    run = tmp_path / "artifacts/gold-matrix-v1"
    # Derived files must be real copies: write mode must never follow a symlink
    # back into the original saved results. Only read-only large inputs link out.
    shutil.copytree(derive.DATA, data)
    shutil.copytree(derive.RUN, run)
    (tmp_path / "data/parkguide.sqlite").symlink_to(ROOT / "data/parkguide.sqlite")
    (tmp_path / "data/evaluation/gold-drafts.jsonl").symlink_to(ROOT / "data/evaluation/gold-drafts.jsonl")
    (tmp_path / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    reports = tmp_path / "reports"
    reports.mkdir()
    for name in evaluate.REPORTS:
        shutil.copyfile(ROOT / "reports" / name, reports / name)
    for module in (assess, derive, report, integrity):
        monkeypatch.setattr(module, "ROOT", tmp_path)
        monkeypatch.setattr(module, "DATA", data)
        monkeypatch.setattr(module, "RUN", run)
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    monkeypatch.setattr(evaluate, "RUN", run)

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline replay must not connect to the network")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    return tmp_path


def saved_hashes(root):
    return {str(p.relative_to(root)): integrity.sha(p)
            for directory in ("data/evaluation/gold-matrix-v1", "artifacts/gold-matrix-v1", "reports")
            for p in (root / directory).rglob("*") if p.is_file()}


def test_replay_writes_consistent_bundle_and_check_preserves_every_file(workspace):
    before = saved_hashes(workspace)
    result = evaluate.replay(write=True)
    assert result["status"] == "written" and result["provider_calls"] == 0
    after = saved_hashes(workspace)
    allowed = {f"artifacts/gold-matrix-v1/{name}" for name in evaluate.ARTIFACTS}
    allowed |= {f"reports/{name}" for name in evaluate.REPORTS}
    assert all(after[name] == digest for name, digest in before.items() if name not in allowed)
    manifest = json.loads((evaluate.RUN / "result-manifest.json").read_text())
    assert all(integrity.sha(workspace / path) == digest
               for path, digest in manifest["artifacts_sha256"].items())
    assert evaluate.replay()["status"] == "pass"
    assert saved_hashes(workspace) == after


@pytest.mark.parametrize("malformed", [False, True])
def test_check_detects_edited_metric_and_missing_report_without_repairing(workspace, malformed):
    evaluate.replay(write=True)
    path = evaluate.RUN / "metrics.json"
    data = json.loads(path.read_text())
    data["action_metrics"]["accuracy"] = 1.0
    path.write_text("broken JSON" if malformed else json.dumps(data))
    (workspace / "reports/GOLD_MATRIX_RESULTS.md").unlink()
    before = saved_hashes(workspace)
    result = evaluate.replay()
    assert result["status"] == "stale"
    assert "artifacts/gold-matrix-v1/metrics.json" in result["changed_files"]
    assert "reports/GOLD_MATRIX_RESULTS.md" in result["changed_files"]
    assert saved_hashes(workspace) == before
    assert evaluate.replay(write=True)["status"] == "written"
    assert evaluate.replay()["status"] == "pass"


def test_invalid_frozen_input_stops_write_before_any_derived_change(workspace):
    path = evaluate.RUN / "chatbot/responses.jsonl"
    path.write_text(path.read_text() + "\n")
    before = saved_hashes(workspace)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        evaluate.replay(write=True)
    assert saved_hashes(workspace) == before


def test_missing_provenance_seal_cannot_bless_changed_metadata(workspace):
    path = evaluate.RUN / "chatbot/metadata.json"
    metadata = json.loads(path.read_text())
    metadata["code_commit"] = "changed historical identity"
    path.write_text(json.dumps(metadata))
    (evaluate.RUN / "result-manifest.json").unlink()
    before = saved_hashes(workspace)
    with pytest.raises(ValueError, match="Missing provenance seal"):
        evaluate.replay(write=True)
    assert saved_hashes(workspace) == before
