"""Portable paired run record for Day 3 offline evaluation."""

from dataclasses import asdict
from typing import Any

from research_compass.evidence import ExplorationReport
from research_compass.exploration import SearchBranch
from research_compass.planning import ResearchIntent
from research_compass.retrieval import SearchOutcome


def build_paired_trace(
    intent: ResearchIntent,
    planned_branches: list[SearchBranch],
    planned: SearchOutcome,
    baseline_branches: list[SearchBranch],
    baseline: SearchOutcome,
    report: ExplorationReport | None,
) -> dict[str, Any]:
    return {
        "schema_version": "day2_paired_v1",
        "interest": intent.original_interest,
        "intent": intent.to_dict(),
        "planned": {
            "branches": [asdict(branch) for branch in planned_branches],
            "search": planned.to_dict(),
            "generation": report.to_dict() if report else None,
        },
        "baseline": {
            "branches": [asdict(branch) for branch in baseline_branches],
            "search": baseline.to_dict(),
        },
    }
