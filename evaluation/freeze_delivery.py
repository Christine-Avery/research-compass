"""Create a one-time, secret-free delivery freeze without changing historical data."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_compass.human_eval import calculate_metrics, parse_yes_no  # noqa: E402


OUT = ROOT / "evaluation" / "freeze" / "final_20261014"
REVIEWED = ROOT / "evaluation" / "reports" / "targeted_review_v1_20261014" / "human_labels_reviewed.csv"
ORIGINAL = ROOT / "evaluation" / "runs" / "v3_20261014" / "human_labels.csv"
TRACE = ROOT / "evaluation" / "cases" / "badcase_001" / "original_trace.json"
EXPECTED_ORIGINAL_SHA = "00168b25e1c614bb9a53b6349a99bb177f145adcf16354b989322e7fe770b0aa"
EXPECTED_TRACE_SHA = "42245808de0b10663652a8d2f28cd27458e4a7aba00c57d78134586e7ef09658"

GP_IDS = {
    "https://openalex.org/W2798274031",
    "https://openalex.org/W2619551236",
}
PENDING_ID = "https://openalex.org/W1888026739"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def create_adjudication(rows: list[dict[str, str]], timestamp: str) -> tuple[list[dict[str, str]], dict]:
    if len(rows) != 35 or len({row["review_id"] for row in rows}) != 35:
        raise ValueError("Expected 35 distinct review records")
    matched = [row for row in rows if row["paper_id"] in GP_IDS | {PENDING_ID}]
    if len(matched) != 3 or {row["paper_id"] for row in matched} != GP_IDS | {PENDING_ID} or any(row["version"] != "V1_Optimized_Rules" for row in matched):
        raise ValueError("Expected exactly three V1 adjudication records")
    final = []
    decisions = []
    for source in rows:
        row = dict(source)
        paper = row["paper_id"]
        before = {
            "human_relevance_label": row["human_relevance_label"],
            "human_evidence_eligible_label": row["human_evidence_eligible_label"],
        }
        if paper in GP_IDS:
            if row["human_relevance_label"] != "2" or row["human_evidence_eligible_label"] != "yes" or row["rule_status"] == "Evidence Eligible":
                raise ValueError(f"Unexpected GP source judgment: {paper}")
            row["human_evidence_eligible_label"] = "no"
            row["adjudication_status"] = "user_confirmed"
            row["adjudication_note"] = "论文相关；用户接受其摘要不准入当前 Evidence Generation。"
        elif paper == PENDING_ID:
            if row["human_relevance_label"] != "2" or row["human_evidence_eligible_label"] != "yes":
                raise ValueError("NLP historical judgment changed; do not infer a decision")
            row["adjudication_status"] = "pending_user_decision"
            row["adjudication_note"] = "相关性与准入标签原样保留；复核理由与标签不一致，待用户最终裁定。"
        else:
            row["adjudication_status"] = "carried_forward"
            row["adjudication_note"] = ""
        if row["adjudication_status"] != "carried_forward":
            decisions.append({
                "review_id": row["review_id"], "paper_id": paper,
                "title": row["title"], "branch": row["branch"], "raw_rank": row["raw_rank"],
                "before": before,
                "after": {
                    "human_relevance_label": row["human_relevance_label"],
                    "human_evidence_eligible_label": row["human_evidence_eligible_label"],
                },
                "status": row["adjudication_status"], "reason": row["adjudication_note"],
                "recorded_at_utc": timestamp,
                "authority": "user instruction in current conversation",
            })
        final.append(row)
    return final, {
        "schema_version": "final_adjudication_v1",
        "status": "pending_one_user_decision",
        "recorded_at_utc": timestamp,
        "source_reviewed_sha256": digest(REVIEWED),
        "original_labels_sha256": digest(ORIGINAL),
        "decisions": decisions,
    }


def gate_metrics(rows: list[dict[str, str]]) -> dict:
    v1 = [row for row in rows if row["version"] == "V1_Optimized_Rules"]
    pending = [row for row in v1 if row["adjudication_status"] == "pending_user_decision"]
    counted = [row for row in v1 if row["adjudication_status"] != "pending_user_decision"]
    if len(v1) != 15 or len(pending) != 1 or any(parse_yes_no(row["human_evidence_eligible_label"]) is None for row in counted):
        raise ValueError("Unexpected adjudication coverage")
    tp = fp = fn = tn = 0
    for row in counted:
        predicted = row["rule_status"] == "Evidence Eligible"
        actual = parse_yes_no(row["human_evidence_eligible_label"]) is True
        if predicted and actual:
            tp += 1
        elif predicted:
            fp += 1
        elif actual:
            fn += 1
        else:
            tn += 1
    ranking = calculate_metrics(rows)["versions"]
    return {
        "schema_version": "final_adjudication_metrics_v1",
        "status": "pending_nlp_adjudication",
        "v1_total": len(v1), "gate_counted": len(counted), "gate_excluded_pending": len(pending),
        "pending_review_ids": [row["review_id"] for row in pending],
        "confusion_on_adjudicated_subset": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "gate_precision": tp / (tp + fp) if tp + fp else None,
        "gate_precision_denominator": tp + fp,
        "gate_recall_final": None,
        "gate_recall_reason": "NLP paper remains unadjudicated; do not report a final denominator or recall",
        "irrelevant_evidence_rate": ranking["V1_Optimized_Rules"]["irrelevant_evidence_rate"],
        "irrelevant_evidence_numerator": ranking["V1_Optimized_Rules"]["irrelevant_evidence_numerator"],
        "irrelevant_evidence_denominator": ranking["V1_Optimized_Rules"]["irrelevant_evidence_denominator"],
        "ranking_status": "provisional_due_to_pending_nlp_relevance",
        "v0_precision_at_5": ranking["V0_Day1_Baseline"]["precision_at_k"],
        "v0_ndcg_at_5": ranking["V0_Day1_Baseline"]["ndcg_at_k"],
        "v1_precision_at_5_provisional": ranking["V1_Optimized_Rules"]["precision_at_k"],
        "v1_ndcg_at_5_provisional": ranking["V1_Optimized_Rules"]["ndcg_at_k"],
        "definitions": {
            "relevance_threshold": 1,
            "ranking_unit": "raw top-5 per branch; macro mean across 4 V0 / 3 V1 branches",
            "gate_positive": "rule_status == Evidence Eligible",
            "gate_reference": "human Evidence Generation yes/no, excluding pending adjudication",
            "gate_precision_denominator": "TP+FP among system-admitted papers",
            "gate_recall_denominator": "TP+FN after all pending labels are resolved",
            "v0_gate": "N/A; no gate existed",
        },
    }


def archive_paths() -> list[Path]:
    fixed = [
        "app.py", "README.md", "requirements.txt", "requirements-dev.txt", ".gitignore",
        ".streamlit/secrets.toml.example",
        "evaluation/cases/badcase_001/original_trace.json",
        "evaluation/cases/badcase_001/expected_intent.json",
        "evaluation/cases/badcase_001/BAD_CASE.md",
        "evaluation/cases/v3_paired_cases.json",
        "evaluation/runs/v3_20261014/live_openalex_golden.json",
        "evaluation/runs/v3_20261014/live_openalex_human_review.csv",
        "evaluation/runs/v3_20261014/human_labels.csv",
        "evaluation/runs/v3_20261014/planner_comparison.json",
        "evaluation/runs/v3_20261014/quality_cost_comparison.json",
        "evaluation/runs/v3_20261014/quality_cost_comparison.md",
        "evaluation/reports/human_review_v0_v1_20261014/labels_snapshot.csv",
        "evaluation/reports/human_review_v0_v1_20261014/metrics.json",
        "evaluation/reports/human_review_v0_v1_20261014/report.md",
        "evaluation/reports/targeted_review_v1_20261014/human_labels_reviewed.csv",
        "evaluation/reports/targeted_review_v1_20261014/metrics.json",
        "evaluation/reports/targeted_review_v1_20261014/report.md",
    ]
    files = [ROOT / name for name in fixed]
    for folder in ("pages", "research_compass", "tests", "evaluation"):
        files.extend((ROOT / folder).glob("*.py"))
    files.extend((ROOT / "evaluation" / "reports" / "targeted_review_v1_20261014" / "changes").glob("*.json"))
    files.extend(path for path in OUT.iterdir() if path.is_file() and path.suffix in {".json", ".csv", ".md"} and path.name != "freeze_manifest.json")
    distinct = sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())
    if any(not path.is_file() for path in distinct):
        raise FileNotFoundError("A frozen source file is missing")
    if any(path.name == ".env" or path.name == "secrets.toml" for path in distinct):
        raise ValueError("A secret path entered the archive")
    return distinct


def main() -> None:
    if digest(ORIGINAL) != EXPECTED_ORIGINAL_SHA or digest(TRACE) != EXPECTED_TRACE_SHA:
        raise ValueError("Historical evidence hash changed; refuse to freeze")
    if any((OUT / name).exists() for name in ("final_adjudication.csv", "adjudication.json", "gate_metrics.json", "source_and_evaluation.zip", "freeze_manifest.json")):
        raise FileExistsError("This delivery freeze already exists; do not overwrite it")
    rows = read_rows(REVIEWED)
    timestamp = datetime.now(timezone.utc).isoformat()
    final, decisions = create_adjudication(rows, timestamp)
    metrics = gate_metrics(final)
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "final_adjudication.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(final[0]))
        writer.writeheader()
        writer.writerows(final)
    (OUT / "adjudication.json").write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "gate_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = archive_paths()
    bundle = OUT / "source_and_evaluation.zip"
    with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    manifest = {
        "schema_version": "research_compass_delivery_freeze_v1",
        "created_at_utc": timestamp,
        "status": "frozen_with_one_pending_human_adjudication",
        "baseline": "Current runnable Streamlit code, with rule planner V1 and archived V0 search baseline",
        "golden_case": "evaluation/cases/badcase_001/original_trace.json and v3 live OpenAlex snapshot",
        "excluded": [".env", ".streamlit/secrets.toml", ".venv", ".git", "__pycache__"],
        "files": {path.relative_to(ROOT).as_posix(): digest(path) for path in files},
        "bundle_path": bundle.relative_to(ROOT).as_posix(),
        "bundle_sha256": digest(bundle),
    }
    (OUT / "freeze_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"frozen_files={len(files)} gate_counted={metrics['gate_counted']} pending={metrics['gate_excluded_pending']}")


if __name__ == "__main__":
    main()
