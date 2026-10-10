#!/usr/bin/env python3
"""Independent, budgeted Azure-only schema and paired embedding smoke check."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import time
import uuid

from dotenv import dotenv_values
import requests
import numpy as np

from parkguide.azure import embed
from parkguide.budget import Budget
from parkguide.runtime import ROOT, config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deployment", default="gpt-6-luna-2026-09-22")
    args = parser.parse_args()
    import os
    for name, value in dotenv_values(ROOT / ".env").items():
        if name.startswith("AZURE_OPENAI_") and value and name not in os.environ:
            os.environ[name] = value
    cfg = config()
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    key = os.getenv("AZURE_OPENAI_API_KEY", "")
    if endpoint != cfg["embedding"]["endpoint"] or not key:
        raise RuntimeError("Approved shared Azure configuration missing; no request sent")
    model = "gpt-6-luna-2026-09-22"
    schema = {"name": "parkguide_connection_check", "strict": True, "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
    }}
    budget = Budget()
    record = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "endpoint": endpoint, "requested_model": model, "requested_deployment": args.deployment,
              "direct_openai_requests": 0, "ledger_before": budget.summary(),
              "attempts": []}
    options = {"temperature": 0, "reasoning_effort": "none", "max_completion_tokens": 128, "store": False}
    # A rejected temperature is recorded before one explicit, temperature-free
    # diagnostic. No automatic model/provider switch or SDK retry is allowed.
    for include_temperature in (True, False):
        request_options = dict(options)
        if not include_temperature:
            request_options.pop("temperature")
        reservation = budget.reserve("generation", 512, 128)
        started = time.perf_counter()
        attempt = {"ledger_event_id": reservation, "options": request_options}
        try:
            response = requests.post(endpoint + "/openai/v1/chat/completions",
                headers={"api-key": key, "Content-Type": "application/json"},
                json={"model": args.deployment, "messages": [{"role": "user", "content": "Return the JSON object with ok set to true."}],
                      "response_format": {"type": "json_schema", "json_schema": schema}, **request_options},
                timeout=(10, 60), allow_redirects=False)
            attempt["http_status"] = response.status_code
            if response.status_code != 200:
                budget.settle(reservation, error=True)
                attempt["error_code"] = "provider_http_error"
            else:
                payload = response.json()
                usage = payload.get("usage", {})
                inputs, outputs = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if any(type(value) is not int or value < 0 for value in (inputs, outputs)):
                    raise ValueError("invalid_usage")
                attempt.update({"returned_model": payload.get("model"), "usage": {"input_tokens": inputs, "output_tokens": outputs},
                                "cost_estimate_usd": budget.settle(reservation, inputs, outputs)})
                choice = payload["choices"][0]
                content = json.loads(choice["message"]["content"])
                attempt["finish_reason"] = choice["finish_reason"]
                attempt["validated"] = payload.get("model") == model and choice["finish_reason"] == "stop" and content == {"ok": True}
        except Exception:
            # Never retain provider bodies, exception strings, headers or keys.
            budget.settle(reservation, error=True)
            attempt["error_code"] = "transport_or_response_validation_error"
        attempt["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        record["attempts"].append(attempt)
        if attempt.get("validated"):
            record["verified_request_options"] = request_options
            break
        if attempt.get("http_status") != 400:
            break
    if record.get("verified_request_options"):
        reservation = budget.reserve("embedding", 64)
        try:
            result = embed(["ParkGuide shared Azure endpoint connection check."], approved_config=cfg["embedding"])
            record["embedding"] = {"ledger_event_id": reservation, "returned_model": result.model,
                "dimension": result.vectors.shape[1], "dtype": str(result.vectors.dtype),
                "finite": bool(np.isfinite(result.vectors).all()),
                "l2_norm": float(np.linalg.norm(result.vectors[0])), "usage": result.usage,
                "elapsed_ms": result.elapsed_ms,
                "cost_estimate_usd": budget.settle(reservation, result.usage["prompt_tokens"])}
        except Exception:
            budget.settle(reservation, error=True)
            record["embedding"] = {"ledger_event_id": reservation, "error_code": "embedding_smoke_failed"}
    record["ledger_after"] = budget.summary()
    record["passed"] = bool(record.get("verified_request_options") and record.get("embedding", {}).get("dimension") == 1536)
    destination = ROOT / "artifacts/setup" / ("azure-luna-smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8] + ".json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"artifact": str(destination.relative_to(ROOT)), **record}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
