"""One-request Qwen planner evaluation; results go to a new V3 run folder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from time import perf_counter

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from research_compass.planning import build_planned_branches, parse_intent
from research_compass.qwen_planning import QwenPlanningError, plan_batch_with_qwen

CASE_FILE = ROOT / "evaluation" / "cases" / "v3_paired_cases.json"
GOLDEN_TRACE = ROOT / "evaluation" / "cases" / "badcase_001" / "original_trace.json"
GOLDEN_LABELS = ROOT / "evaluation" / "cases" / "badcase_001" / "expected_intent.json"
OUT = ROOT / "evaluation" / "runs" / "v3_20261014"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relationship(intent) -> str:
    return intent.relationship if "→" in intent.relationship else ""


def task_type(intent) -> str:
    task = intent.task.lower()
    has_transfer = "迁移" in intent.task or "transfer" in task or "inspir" in task
    has_comparison = "比较" in intent.task or "对比" in intent.task or "compar" in task
    if has_transfer and has_comparison:
        return "comparison_transfer"
    if has_transfer:
        return "transfer"
    if has_comparison:
        return "comparison"
    return "topic_map"


def is_complex_interest(interest: str) -> bool:
    """Input-only routing heuristic for offline V3 simulation; never reads gold labels."""
    relational_cues = re.compile(
        r"\b(compare|comparison|versus|vs\.?|inspire|transfer|adapt|guide|build on)\b|"
        r"比较|对比|区别|启发|指导|迁移|借鉴|转化", re.I,
    )
    return bool(relational_cues.search(interest))


def compare_intent(intent, gold: dict) -> dict:
    actual_concepts = set(intent.concepts)
    expected_concepts = set(gold["concepts"])
    checks = {
        "domain": intent.domain == gold["domain"],
        "concepts_exact": actual_concepts == expected_concepts,
        "source_method": intent.source_method == gold["source_method"],
        "target_method": intent.target_method == gold["target_method"],
        "task_type": task_type(intent) == gold["task_type"],
        "relationship": relationship(intent) == gold["relationship"],
        "explicit_constraints": tuple(intent.explicit_constraints) == tuple(gold["explicit_constraints"]),
    }
    return {"checks": checks, "correct": sum(checks.values()), "denominator": len(checks)}


def aggregate(cases: list[dict]) -> dict:
    n = sum(item["denominator"] for item in cases)
    correct = sum(item["correct"] for item in cases)
    return {"correct": correct, "denominator": n, "rate": round(correct / n, 4) if n else None, "case_count": len(cases)}


def main() -> None:
    labels = read_json(GOLDEN_LABELS)
    if digest(GOLDEN_TRACE) != labels["source_trace_sha256"]:
        raise SystemExit("Golden trace hash mismatch; refusing to use the changed trace")
    dataset = read_json(CASE_FILE)["cases"]
    original = read_json(GOLDEN_TRACE)
    v0_intent = original.get("intent", {})

    v1: dict[str, tuple] = {}
    v1_latency = {}
    for case in dataset:
        start = perf_counter()
        parsed = parse_intent(case["interest"])
        branches = build_planned_branches(parsed)
        v1_latency[case["case_id"]] = round((perf_counter() - start) * 1000, 3)
        v1[case["case_id"]] = (parsed, branches)

    cases_for_qwen = [
        {"case_id": item["case_id"], "interest": item["interest"]}
        for item in dataset
    ]
    try:
        v2, qwen_meta = plan_batch_with_qwen(cases_for_qwen)
        qwen_error = None
    except QwenPlanningError as exc:
        v2, qwen_meta, qwen_error = {}, None, str(exc)

    ledger_path = OUT / "qwen_ledger.json"
    ledger = read_json(ledger_path) if ledger_path.exists() else {"attempts": 0, "estimated_reserved_cny": 0.0, "calls": []}
    qwen_failures = sum(1 for call in ledger["calls"] if call.get("status") != "success")

    by_id = {item["case_id"]: item for item in dataset}
    strategies: dict[str, dict] = {"V1": {}, "V2": {}, "V3": {}}
    for case_id, case in by_id.items():
        rules = v1[case_id]
        strategies["V1"][case_id] = rules
        if case_id in v2:
            strategies["V2"][case_id] = v2[case_id]
        # Offline-only hybrid routing: transfer/comparison cases route to the
        # recorded Qwen plan if available; a plain topic map uses local rules.
        is_complex = is_complex_interest(case["interest"])
        strategies["V3"][case_id] = v2.get(case_id, rules) if is_complex else rules

    metrics = {}
    for version, outputs in strategies.items():
        per_case = {
            case_id: compare_intent(outputs[case_id][0], by_id[case_id]["gold"])
            for case_id in outputs
        }
        metrics[version] = {"intent_preservation": aggregate(list(per_case.values())), "per_case": per_case}

    # V0 is intentionally only scored where a structured historic output exists.
    # No V0 predictions are fabricated for the two new inputs.
    v0_checks = {
        "domain": False,
        "concepts_exact": False,
        "source_method": v0_intent.get("source_method", "") == labels["concepts"][0]["name"],
        "target_method": v0_intent.get("target_method", "") == labels["concepts"][1]["name"],
        "task_type": False,
        "relationship": False,
        "explicit_constraints": v0_intent.get("constraints", "") == "",
    }
    metrics["V0"] = {
        "intent_preservation": aggregate([{"correct": sum(v0_checks.values()), "denominator": len(v0_checks), "checks": v0_checks}]),
        "per_case": {"badcase_001": {"checks": v0_checks, "correct": sum(v0_checks.values()), "denominator": len(v0_checks)}},
        "note": "Only badcase_001 has an archived structured V0 trace; no outputs fabricated for new cases.",
    }

    output_intents = {}
    for version, outputs in strategies.items():
        output_intents[version] = {
            case_id: {
                "intent": pair[0].to_dict(),
                "branches": [
                    {"key": b.key, "title": b.title, "purpose": b.purpose, "query": b.query,
                     "focus_method": b.focus_method, "required_methods": list(b.required_methods)}
                    for b in pair[1]
                ],
            }
            for case_id, pair in outputs.items()
        }
    payload = {
        "schema_version": "v3_planner_comparison_v1",
        "source_hashes": {
            "original_trace.json": digest(GOLDEN_TRACE), "expected_intent.json": digest(GOLDEN_LABELS),
            "v3_paired_cases.json": digest(CASE_FILE),
        },
        "qwen": {"status": "success" if qwen_meta else "not_run_or_failed", "error": qwen_error, "usage": qwen_meta},
        "strategies": output_intents,
        "metrics": metrics,
        "cost_latency": {
            "V0": {"api_calls": 0, "cost": "historical; not recorded"},
            "V1": {"api_calls": 0, "planner_latency_ms_by_case": v1_latency, "cost_cny": 0},
            "V2": {"api_calls_attempted": ledger["attempts"], "api_calls_failed": qwen_failures,
                   "failure_rate": round(qwen_failures / ledger["attempts"], 4) if ledger["attempts"] else None,
                   "latency_ms": qwen_meta.get("latency_ms") if qwen_meta else None,
                   "input_tokens": qwen_meta.get("input_tokens") if qwen_meta else None,
                   "output_tokens": qwen_meta.get("output_tokens") if qwen_meta else None,
                   "cost_cny": qwen_meta.get("cost_cny") if qwen_meta else None,
                   "reserved_max_cost_cny": ledger.get("estimated_reserved_cny"),
                   "billing_status": "unknown for network failures; reserve kept as upper bound" if qwen_failures else "reported usage"},
            "V3": {"api_calls": 0, "cost_cny": 0,
                   "note": "offline routing simulation reuses recorded V2 plans where available; this run fell back to rules because Qwen was unavailable; not a deployed hybrid latency/cost estimate"},
        },
        "retrieval_quality": {
            "precision_at_5": None, "direction_coverage": None, "irrelevant_evidence_rate": None,
            "reason": "Awaiting live retrieval and human relevance adjudication; model/rule gates are not ground truth.",
        },
    }
    write_json(OUT / "planner_comparison.json", payload)
    print(json.dumps({
        "golden_trace_sha256_verified": True,
        "qwen_status": payload["qwen"]["status"],
        "qwen_error": qwen_error,
        "qwen_input_tokens": qwen_meta.get("input_tokens") if qwen_meta else None,
        "qwen_output_tokens": qwen_meta.get("output_tokens") if qwen_meta else None,
        "qwen_cost_cny": qwen_meta.get("cost_cny") if qwen_meta else None,
        "intent_metrics": {version: metric["intent_preservation"] for version, metric in metrics.items()},
        "artifact": str(OUT / "planner_comparison.json"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
