"""One bounded, blinded Claude Code CLI labeling run; never calls ParkGuide."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/ai-labeling/sample-v1/claude-code"


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    if (OUT / "cli-response.json").exists():
        raise SystemExit("Refusing to overwrite a completed CLI run")
    manifest = json.loads((OUT.parent / "run-manifest.json").read_text())
    work = Path(manifest["workspaces"]["claude-code"])
    packet = (work / "annotation-input.json").read_bytes()
    assert hashlib.sha256(packet).hexdigest() == manifest["input_sha256"]
    executable = shutil.which("claude")
    if not executable:
        raise SystemExit("Claude Code CLI not installed")
    version = subprocess.check_output([executable, "--version"], text=True).strip()
    instructions = (work / "instructions.txt").read_text()
    schema = json.dumps(json.loads((work / "labels.schema.json").read_text()), separators=(",", ":"))
    (work / "empty-mcp.json").write_text('{"mcpServers":{}}\n')
    command = [executable, "-p", "--safe-mode", "--tools", "", "--disable-slash-commands", "--no-chrome", "--strict-mcp-config", "--mcp-config", str(work / "empty-mcp.json"), "--no-session-persistence", "--permission-mode", "dontAsk", "--permission-prompts", "none", "--output-format", "json", "--json-schema", schema, "--max-budget-usd", "3", "--system-prompt", instructions]
    provenance = {"reviewer_id": "claude-code", "input_sha256": manifest["input_sha256"], "cli_version": version, "started_at": utc(), "model_selection": "configured default; no override or fallback requested", "tools": [], "safe_mode": True, "api_budget_cap_usd": 3, "human_review_pending": True, "status": "running", "prompt_sha256": hashlib.sha256(instructions.encode()).hexdigest(), "schema_sha256": hashlib.sha256((work / "labels.schema.json").read_bytes()).hexdigest()}
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"status": "running", "reviewer": "claude-code", "input_bytes": len(packet), "cli_version": version}), flush=True)
    started = time.monotonic()
    try:
        response = subprocess.run(command, input=packet.decode(), cwd=work, text=True, capture_output=True, timeout=600)
        provenance.update(finished_at=utc(), elapsed_seconds=round(time.monotonic() - started, 3), exit_code=response.returncode)
        result = json.loads(response.stdout)
        if response.returncode or result.get("is_error") or not isinstance(result.get("structured_output"), dict):
            provenance.update(status="failed", result_type=result.get("type"), result_subtype=result.get("subtype"), total_cost_usd=result.get("total_cost_usd"), stderr_present=bool(response.stderr))
            raise RuntimeError("CLI did not return a successful structured label set; no semantic retry")
        # Preserve actual CLI result before any root normalization/validation.
        (OUT / "cli-response.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        (OUT / "labels.json").write_text(json.dumps(result["structured_output"], ensure_ascii=False, indent=2) + "\n")
        provenance.update(status="completed", total_cost_usd=result.get("total_cost_usd"), usage=result.get("usage"), model_usage=result.get("modelUsage"), cli_turn_count=result.get("num_turns"), duration_api_ms=result.get("duration_api_ms"), limitations="AI proposals from a supplied saved-source packet; no human validation or live source access. CLI total_cost_usd is provider/CLI-reported, not a billing invoice.")
    except (subprocess.TimeoutExpired, ValueError, RuntimeError) as exc:
        provenance.update(status="failed", finished_at=utc(), error_type=type(exc).__name__, elapsed_seconds=round(time.monotonic() - started, 3))
        (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        raise SystemExit("Claude labeling failed; sanitized provenance saved; no automatic retry")
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"status": provenance["status"], "label_count": len(result["structured_output"].get("labels", [])), "models": list((result.get("modelUsage") or {}).keys()), "reported_cost_usd": result.get("total_cost_usd"), "elapsed_seconds": provenance["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
