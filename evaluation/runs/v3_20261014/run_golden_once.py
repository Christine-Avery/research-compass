"""One bounded, manually invoked Golden Case Qwen check; never auto-retries."""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from dotenv import load_dotenv

from research_compass.qwen_planning import LEDGER, QwenPlanningError, plan_with_qwen


ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
trace = json.loads((ROOT / "evaluation/cases/badcase_001/original_trace.json").read_text(encoding="utf-8"))
ledger_before = json.loads(LEDGER.read_text(encoding="utf-8"))
print(json.dumps({"attempts_before": ledger_before["attempts"], "reserved_cny_before": ledger_before["estimated_reserved_cny"]}))

try:
    intent, branches, metadata = plan_with_qwen(trace["interest"])
    result = {
        "case_id": "badcase_001", "source": "live_qwen", "created_at": datetime.now(timezone.utc).isoformat(),
        "intent": asdict(intent), "branches": [asdict(branch) for branch in branches],
        "metadata": metadata,
    }
    output = Path(__file__).with_name("golden_qwen_live_20261014.json")
    if output.exists():
        raise RuntimeError("Live result already exists; refusing to overwrite it")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "success", "call_id": metadata["call_id"],
                      "latency_ms": metadata["latency_ms"], "input_tokens": metadata["input_tokens"],
                      "output_tokens": metadata["output_tokens"], "cost_cny": metadata["cost_cny"],
                      "intent": {key: getattr(intent, key) for key in ("domain", "source_method", "target_method", "relationship", "explicit_constraints")},
                      "queries": [branch.query for branch in branches]}, ensure_ascii=False))
except QwenPlanningError as exc:
    print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False))
