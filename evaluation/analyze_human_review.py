"""Recalculate the frozen V0/V1 human review without altering annotations.

Usage: python evaluation/analyze_human_review.py INPUT.csv --output METRICS.json
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from hashlib import sha256
import json
from math import log2
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_compass.human_eval import calculate_metrics, parse_relevance, parse_yes_no  # noqa: E402


def brief(row: dict[str, str]) -> dict[str, str]:
    return {key: row.get(key, "") for key in (
        "version", "branch", "raw_rank", "paper_id", "title", "rule_status",
        "human_relevance_label", "human_evidence_eligible_label", "evidence_reason", "review_status",
    )}


def analyze(path: Path) -> dict:
    raw = path.read_bytes()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("The review CSV contains no rows")

    versions = list(dict.fromkeys(row["version"] for row in rows))
    branches = []
    for version in versions:
        for branch in dict.fromkeys(row["branch"] for row in rows if row["version"] == version):
            top = sorted(
                (row for row in rows if row["version"] == version and row["branch"] == branch),
                key=lambda row: int(row["raw_rank"]),
            )[:5]
            scores = [parse_relevance(row.get("human_relevance_label")) for row in top]
            complete = bool(top) and all(score is not None for score in scores)
            precision = ndcg = None
            if complete:
                precision = sum(score >= 1 for score in scores) / 5
                gains = [2**score - 1 for score in scores]
                dcg = sum(gain / log2(rank + 2) for rank, gain in enumerate(gains))
                ideal = sum(gain / log2(rank + 2) for rank, gain in enumerate(sorted(gains, reverse=True)))
                ndcg = dcg / ideal if ideal else 0.0
            branches.append({
                "version": version, "branch": branch, "returned_top_5": len(top),
                "judged_top_5": sum(score is not None for score in scores),
                "scores_in_raw_rank_order": scores,
                "precision_at_5": precision, "ndcg_at_5": ndcg,
            })

    v1 = [row for row in rows if row["version"] == "V1_Optimized_Rules"]
    admitted = [row for row in v1 if row.get("rule_status") == "Evidence Eligible"]
    reviewed_gate = [row for row in v1 if parse_yes_no(row.get("human_evidence_eligible_label")) is not None]
    false_accepts = [row for row in reviewed_gate if row.get("rule_status") == "Evidence Eligible" and parse_yes_no(row.get("human_evidence_eligible_label")) is False]
    false_rejects = [row for row in reviewed_gate if row.get("rule_status") != "Evidence Eligible" and parse_yes_no(row.get("human_evidence_eligible_label")) is True]
    contradictions = [row for row in rows if parse_relevance(row.get("human_relevance_label")) == 0 and parse_yes_no(row.get("human_evidence_eligible_label")) is True]
    incomplete = [row for row in rows if parse_relevance(row.get("human_relevance_label")) is None or parse_yes_no(row.get("human_evidence_eligible_label")) is None]

    return {
        "schema_version": "human_review_analysis_v1",
        "input_sha256": sha256(raw).hexdigest(),
        "row_count": len(rows),
        "review_status_counts": dict(Counter(row.get("review_status", "") for row in rows)),
        "relevance_judged": sum(parse_relevance(row.get("human_relevance_label")) is not None for row in rows),
        "evidence_judged": sum(parse_yes_no(row.get("human_evidence_eligible_label")) is not None for row in rows),
        "both_judged": len(rows) - len(incomplete),
        "explicit_skipped": sum(row.get("review_status") == "skipped" for row in rows),
        "incomplete": [brief(row) for row in incomplete],
        "relevance_counts_by_version": {
            version: dict(Counter(row.get("human_relevance_label", "") for row in rows if row["version"] == version))
            for version in versions
        },
        "unique_paper_ids_by_version": {
            version: len({row.get("paper_id") for row in rows if row["version"] == version})
            for version in versions
        },
        "ranking_metrics": calculate_metrics(rows, k=5),
        "branch_metrics": branches,
        "v1_gate_audit": {
            "admitted_total": len(admitted),
            "admitted_with_relevance_label": sum(parse_relevance(row.get("human_relevance_label")) is not None for row in admitted),
            "gate_judged_total": len(reviewed_gate),
            "human_eligible_yes": sum(parse_yes_no(row.get("human_evidence_eligible_label")) is True for row in reviewed_gate),
            "human_eligible_no": sum(parse_yes_no(row.get("human_evidence_eligible_label")) is False for row in reviewed_gate),
            "false_accepts": [brief(row) for row in false_accepts],
            "false_rejects": [brief(row) for row in false_rejects],
            "relevant_false_rejects": [brief(row) for row in false_rejects if parse_relevance(row.get("human_relevance_label")) in (1, 2)],
        },
        "annotation_conflicts_relevance_0_evidence_yes": [brief(row) for row in contradictions],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.input)
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
