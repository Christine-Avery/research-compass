"""Regenerate the corrected-label report from frozen labels and human events."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_compass.targeted_report import write_report  # noqa: E402


if __name__ == "__main__":
    result = write_report(
        ROOT / "evaluation" / "runs" / "v3_20261014" / "human_labels.csv",
        ROOT / "evaluation" / "reports" / "targeted_review_v1_20261014",
    )
    print(f"status={result['status']} reviewed={result['reviewed_candidate_count']}/{result['candidate_count']}")
