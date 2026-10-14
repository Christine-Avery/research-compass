"""Assemble quality/cost report from recorded V3 evaluation artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "evaluation" / "runs" / "v3_20261014"


def read(name: str):
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def main() -> None:
    planners = read("planner_comparison.json")
    live = read("live_openalex_golden.json")
    ledger = read("qwen_ledger.json")
    review_path = RUN / "live_openalex_human_review.csv"
    with review_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    completed_reviews = sum(bool(row.get("human_relevance_label", "").strip()) for row in rows)

    v0 = live["strategies"]["V0_Day1_Baseline"]
    v1 = live["strategies"]["V1_Optimized_Rules"]
    v1_branches = v1["search"]["queries"]
    v1_eligible = sum(bool(hit.get("evidence_eligible")) for query in v1_branches for hit in query["ranked_results"])
    covered_directions = sum(
        any(hit.get("evidence_eligible") for hit in query["ranked_results"])
        for query in v1_branches
    )
    branch_failures = {
        key: {"failures": sum(bool(q.get("error")) for q in item["search"]["queries"]), "queries": len(item["search"]["queries"])}
        for key, item in live["strategies"].items()
    }
    v1_intent = planners["metrics"]["V1"]["intent_preservation"]
    v0_intent = planners["metrics"]["V0"]["intent_preservation"]
    v3_intent = planners["metrics"]["V3"]["intent_preservation"]
    qwen_failures = sum(call.get("status") != "success" for call in ledger["calls"])

    table = [
        {
            "version": "V0 · archived rules",
            "intent_preservation": f"{v0_intent['correct']}/{v0_intent['denominator']} (n=1 archived case)",
            "precision_at_5": "待人工标注",
            "direction_coverage": "N/A · no structured directions / gate",
            "irrelevant_evidence_rate": "待人工标注",
            "latency": f"{v0['end_to_end_ms']:.0f} ms, 1 Live run (4 queries)",
            "cost": "LLM ¥0; OpenAlex no charge recorded",
            "failure_rate": f"{branch_failures['V0_Day1_Baseline']['failures']}/{branch_failures['V0_Day1_Baseline']['queries']} query failures",
        },
        {
            "version": "V1 · optimized rules",
            "intent_preservation": f"{v1_intent['correct']}/{v1_intent['denominator']} (n=3; hand-authored paired set)",
            "precision_at_5": "待人工标注",
            "direction_coverage": f"{covered_directions}/3 (provisional gate coverage; 3 branches)",
            "irrelevant_evidence_rate": "待人工标注",
            "latency": f"{v1['end_to_end_ms']:.0f} ms, 1 Live run (3 queries); parser avg {sum(planners['cost_latency']['V1']['planner_latency_ms_by_case'].values())/3:.2f} ms",
            "cost": "LLM ¥0; OpenAlex no charge recorded",
            "failure_rate": f"{branch_failures['V1_Optimized_Rules']['failures']}/{branch_failures['V1_Optimized_Rules']['queries']} query failures",
        },
        {
            "version": "V2 · Qwen planner",
            "intent_preservation": "N/A · no valid Qwen response",
            "precision_at_5": "N/A · no V2 retrieval",
            "direction_coverage": "N/A",
            "irrelevant_evidence_rate": "N/A",
            "latency": "N/A · no successful response",
            "cost": f"2 attempted; usage/bill unknown; reserve upper bound ¥{ledger['estimated_reserved_cny']:.5f}",
            "failure_rate": f"{qwen_failures}/{ledger['attempts']} Qwen request failures (URLError)",
        },
        {
            "version": "V3 · hybrid (offline simulation)",
            "intent_preservation": f"{v3_intent['correct']}/{v3_intent['denominator']} (n=3; rules fallback this run)",
            "precision_at_5": "待人工标注; no separate retrieval",
            "direction_coverage": f"{covered_directions}/3 inherited from V1 fallback; provisional",
            "irrelevant_evidence_rate": "待人工标注",
            "latency": "N/A · routing only; no deployed E2E measurement",
            "cost": "Incremental simulation ¥0; deployed hybrid cost unmeasured",
            "failure_rate": "Qwen unavailable; all routed cases fell back to rules",
        },
    ]
    result = {
        "schema_version": "v3_quality_cost_report_v1",
        "sample_size": {"V0_intent": 1, "V1_intent": 3, "V2_intent": 0, "V3_intent": 3,
                        "live_openalex_Golden": 1, "manual_review_rows": len(rows), "manual_review_completed": completed_reviews},
        "intent_preservation_formula": "Exact slot matches / (7 annotated slots per case); slots: domain, exact concept set, source, target, task type, directed relationship, explicit-constraint set.",
        "precision_at_5_formula": "Human-labelled relevant items in ranks 1-5 / all human-labelled items in ranks 1-5, per strategy.",
        "direction_coverage_formula": "Expected Golden directions with >=1 Evidence Eligible result / 3 directions (source method, target method, comparison/transfer). Provisional until human review.",
        "irrelevant_evidence_rate_formula": "Human-labelled irrelevant Evidence Eligible items / all manually judged Evidence Eligible items.",
        "human_review_complete": completed_reviews,
        "v1_gate_eligible_occurrences": v1_eligible,
        "qwen_attempts": ledger["attempts"], "qwen_failures": qwen_failures,
        "qwen_reserved_max_cny": ledger["estimated_reserved_cny"],
        "strategies": table,
        "limitations": [
            "The three manually authored intent cases are a small smoke set, not a representative benchmark; no significance claim is supported.",
            "V0 intent is measurable only on the one archived structured trace. V0 retrieval is a new Live replay of its saved legacy query strings.",
            "Precision@5 and irrelevant-evidence rate are intentionally null pending human labels; automated relevance scores are not reference labels.",
            "V2 has no valid model output, so this run cannot answer whether Qwen improves quality or whether its cost is worthwhile.",
            "V3 is offline only. Because Qwen failed, it fell back to V1 rules; its score is not evidence of hybrid-model quality.",
        ],
        "source_files": ["planner_comparison.json", "live_openalex_golden.json", "qwen_ledger.json", "live_openalex_human_review.csv"],
    }
    (RUN / "quality_cost_comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Research Compass V3 — Quality and Cost Comparison", "",
        "Run date: 2026-10-14. Golden source hash verified; original trace remains read-only.", "",
        "| Strategy | Intent Preservation | Precision@5 | Direction Coverage | Irrelevant Evidence Rate | Latency | Cost / Failure |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for item in table:
        lines.append(
            f"| {item['version']} | {item['intent_preservation']} | {item['precision_at_5']} | "
            f"{item['direction_coverage']} | {item['irrelevant_evidence_rate']} | {item['latency']} | "
            f"{item['cost']}<br>{item['failure_rate']} |"
        )
    lines += [
        "", "## Metric definitions and sample sizes", "",
        "- **Intent Preservation:** exact matched slots / seven annotated slots per case: domain, exact concept set, source, target, task type, directed relation, explicit constraints. V0 n=1; V1/V3 n=3; V2 n=0 valid responses.",
        "- **Precision@5:** manually labelled relevant records / manually labelled records in each branch's raw ranks 1–5. No percentage is reported while labels are blank.",
        "- **Direction Coverage:** expected Golden directions with at least one Evidence Eligible result / 3 (source, target, comparison/transfer). Automated gate count only; human confirmation is pending.",
        "- **Irrelevant Evidence Rate:** manually judged irrelevant Evidence Eligible papers / all manually judged Evidence Eligible papers. `live_openalex_human_review.csv` has " + str(len(rows)) + " rows and " + str(completed_reviews) + " completed labels.",
        "- **Latency:** one live OpenAlex run, including planning plus retrieval for V1; single-run timings are noisy and not a performance claim. Qwen has no successful response latency.",
        "- **Cost:** official Qwen3.8-Flash list price was ¥0.8/M input and ¥2.7/M output tokens. Requests were capped at 4,500 input and 1,800 output tokens: at most ¥0.00846 per request, or ¥0.0423 across the five-call limit. Two failed attempts returned no usage, so actual billing is unknown; ¥" + f"{ledger['estimated_reserved_cny']:.5f}" + " remains reserved as an upper bound for this run.",
        "", "## Live retrieval and failures", "",
        f"- OpenAlex key status: loaded (boolean only). V0 returned {len(v0['search']['papers'])} unique papers in Live mode; V1 returned {len(v1['search']['papers'])} unique papers in Live mode. V1 rule gate marked {v1_eligible} branch-ranked candidates Evidence Eligible across 3 branches (source/target/comparison coverage {covered_directions}/3). These are model gate outputs, not human precision labels.",
        "- V1 did not admit any paper from the combined comparison/transfer branch. The report says evidence is insufficient for that direction; it does not infer a research gap.",
        "- The archived V0 query results include plainly unrelated title/abstract candidates. V0 had no relevance/evidence gate; its 13 unique results are retrievals, not evidence.",
        f"- Qwen3.8-Flash network calls: {ledger['attempts']} attempted, {qwen_failures} failed with URLError; no auto-retry; token usage and bill unknown. The cumulative attempt count remains under the hard five-call cap.",
        "- V3 used an input-wording-only routing heuristic in offline simulation (relational cues to Qwen; plain map queries to rules). Since Qwen was unavailable, routed cases fell back to rules. No Qwen quality lift or hybrid deployed cost is established.",
        "", "## Reproduce", "",
        "```powershell", ".venv\\Scripts\\python.exe -m pytest -q", ".venv\\Scripts\\python.exe evaluation\\run_v3_intent_comparison.py", ".venv\\Scripts\\python.exe evaluation\\run_v3_live_openalex.py", ".venv\\Scripts\\python.exe evaluation\\write_v3_comparison_report.py", "```", "",
        "The Qwen comparison script consumes the bounded Qwen call ledger; do not rerun it after network failure unless intentionally spending another allowed attempt. The Golden Trace is only read and hash-checked.", "",
        "## Manual review", "",
        "Fill `live_openalex_human_review.csv` using the actual title and abstract. Label relevance to the intended domain/method/direction, evidence eligibility, and claim support separately. Do not use the rule score as the label.", "",
    ]
    (RUN / "quality_cost_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"report": str(RUN / "quality_cost_comparison.md"), "manual_review_rows": len(rows), "labels_completed": completed_reviews}, ensure_ascii=False))


if __name__ == "__main__":
    main()
