"""File-locked API reservations, priced estimates, and a resumable ledger."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import uuid

from .runtime import ROOT, config, ledger_path


class Budget:
    def __init__(self, root=None, cap=None):
        # Pricing always comes from root's config; the default ledger follows
        # the runtime profile (repository locally, per-instance /tmp hosted).
        self.root = Path(root) if root is not None else ROOT
        self.cap = cap if cap is not None else config()["evaluation"]["proposed_api_budget_usd"]
        self.path = ledger_path() if root is None else self.root / "artifacts/api-ledger.json"

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            ledger = json.loads(self.path.read_text()) if self.path.exists() else {"events": []}
            yield ledger
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(ledger, indent=2) + "\n")
            temporary.replace(self.path)

    def rates(self, kind):
        pricing = self.root / "config/pricing.json"
        if not pricing.exists():
            raise RuntimeError("Published price metadata is missing; paid calls disabled")
        rates = json.loads(pricing.read_text()).get(kind)
        if not rates or rates.get("input_per_million_usd") is None:
            raise RuntimeError("Provider price metadata is missing; paid calls disabled")
        return rates

    def reserve(self, kind, input_upper, output_upper=0):
        rates = self.rates(kind)
        maximum = (input_upper * rates["input_per_million_usd"] + output_upper * rates.get("output_per_million_usd", 0)) / 1_000_000
        with self.locked() as ledger:
            committed = sum(event["cost_estimate_usd"] for event in ledger["events"])
            if committed + maximum > self.cap:
                raise RuntimeError("API budget cap reached; no request sent")
            identifier = uuid.uuid4().hex
            ledger["events"].append({"id": identifier, "kind": kind, "timestamp": datetime.now(timezone.utc).isoformat(), "status": "reserved", "cost_estimate_usd": maximum, "rates": rates})
        return identifier

    def settle(self, identifier, input_tokens=None, output_tokens=0, error=False):
        with self.locked() as ledger:
            event = next(item for item in ledger["events"] if item["id"] == identifier)
            if input_tokens is not None:
                rates = event["rates"]
                event["cost_estimate_usd"] = (input_tokens * rates["input_per_million_usd"] + output_tokens * rates.get("output_per_million_usd", 0)) / 1_000_000
                event["input_tokens"] = input_tokens
                event["output_tokens"] = output_tokens
            event["status"] = "provider_error_reserved" if error else "reported_usage"
            return event["cost_estimate_usd"]

    def summary(self):
        with self.locked() as ledger:
            total = sum(event["cost_estimate_usd"] for event in ledger["events"])
            return {"cap_usd": self.cap, "estimated_committed_usd": total, "remaining_estimated_usd": self.cap - total, "events": len(ledger["events"]), "basis": "published prices and provider token usage; not a billing statement"}
