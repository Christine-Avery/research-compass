"""Targeted human re-review on top of an immutable 35-row annotation snapshot."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

from research_compass.human_eval import calculate_metrics, parse_relevance, parse_yes_no


SNAPSHOT_SHA256 = "00168b25e1c614bb9a53b6349a99bb177f145adcf16354b989322e7fe770b0aa"
EDIT_FIELDS = ("human_relevance_label", "human_evidence_eligible_label", "evidence_reason", "reviewer", "review_status")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def snapshot_rows(path: Path) -> list[dict[str, str]]:
    if sha256(path.read_bytes()).hexdigest() != SNAPSHOT_SHA256:
        raise ValueError("Original human_labels.csv changed; targeted review has stopped to protect the baseline")
    rows = read_csv(path)
    if len(rows) != 35 or len({row["review_id"] for row in rows}) != 35:
        raise ValueError("Expected 35 distinct baseline review records")
    return rows


def candidates(rows: list[dict[str, str]]) -> list[tuple[str, str]]:
    """Select V1 conflicts, missing gate judgment, and relevant gate rejects."""
    selected = []
    for row in rows:
        if row.get("version") != "V1_Optimized_Rules":
            continue
        relevance = parse_relevance(row.get("human_relevance_label"))
        eligible = parse_yes_no(row.get("human_evidence_eligible_label"))
        category = None
        if relevance == 0 and eligible is True:
            category = "相关性 0 / 证据准入是：标注冲突"
        elif eligible is None:
            category = "证据准入未判断"
        elif relevance in (1, 2) and eligible is True and row.get("rule_status") != "Evidence Eligible":
            category = "已检出但被 Gate 拒绝：直接相关或跨领域边界"
        if category:
            selected.append((row["review_id"], category))
    return selected


def load_reviewed(snapshot_path: Path, events_dir: Path) -> tuple[list[dict[str, str]], set[str]]:
    rows = snapshot_rows(snapshot_path)
    by_id = {row["review_id"]: row for row in rows}
    reviewed_ids: set[str] = set()
    for path in sorted(events_dir.glob("*.json")) if events_dir.exists() else []:
        event = json.loads(path.read_text(encoding="utf-8"))
        if event.get("snapshot_sha256") != SNAPSHOT_SHA256:
            raise ValueError(f"Wrong baseline hash in review event {path.name}")
        rid = event["review_id"]
        if rid not in by_id:
            raise ValueError(f"Unknown review ID in {path.name}")
        row = by_id[rid]
        if {field: row.get(field, "") for field in EDIT_FIELDS} != event["before"]:
            raise ValueError(f"Review history diverged at {path.name}")
        row.update(event["after"])
        reviewed_ids.add(rid)
    return rows, reviewed_ids


def write_reviewed_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def save_review(
    snapshot_path: Path,
    events_dir: Path,
    output_csv: Path,
    review_id: str,
    expected_before: dict[str, str],
    after: dict[str, str],
    change_reason: str,
) -> dict:
    if os.getenv("PUBLIC_DEPLOYMENT", "false").lower() == "true":
        raise PermissionError("Public Evaluation is read-only")
    if not change_reason.strip():
        raise ValueError("A human review reason is required, including when labels stay unchanged")
    rows, _ = load_reviewed(snapshot_path, events_dir)
    candidate_ids = {rid for rid, _ in candidates(snapshot_rows(snapshot_path))}
    if review_id not in candidate_ids:
        raise ValueError("This record is outside the targeted review set")
    row = next(row for row in rows if row["review_id"] == review_id)
    before = {field: row.get(field, "") for field in EDIT_FIELDS}
    if before != expected_before:
        raise ValueError("The review changed in another session; reload before saving")
    if set(after) != set(EDIT_FIELDS):
        raise ValueError("Review fields are incomplete")
    if parse_relevance(after["human_relevance_label"]) is None:
        raise ValueError("Choose a relevance score 0, 1, or 2")
    if after["human_evidence_eligible_label"] not in ("yes", "no", ""):
        raise ValueError("Choose yes/no or leave the evidence judgment open")
    after = {field: str(after[field]) for field in EDIT_FIELDS}
    after["review_status"] = "complete" if after["human_evidence_eligible_label"] else "in_progress"
    event = {
        "schema_version": "targeted_human_review_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_sha256": SNAPSHOT_SHA256,
        "review_id": review_id,
        "version": row["version"],
        "branch": row["branch"],
        "raw_rank": row["raw_rank"],
        "paper_id": row["paper_id"],
        "before": before,
        "after": after,
        "change_reason": change_reason.strip(),
    }
    events_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex + ".json"
    with (events_dir / filename).open("x", encoding="utf-8") as handle:
        json.dump(event, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    revised, _ = load_reviewed(snapshot_path, events_dir)
    write_reviewed_csv(revised, output_csv)
    return event


def gate_metrics(rows: list[dict[str, str]]) -> dict:
    """V1 confusion counts on rows with an explicit human evidence judgment."""
    v1 = [row for row in rows if row.get("version") == "V1_Optimized_Rules"]
    judged = [row for row in v1 if parse_yes_no(row.get("human_evidence_eligible_label")) is not None]
    tp = fp = fn = tn = 0
    for row in judged:
        predicted = row.get("rule_status") == "Evidence Eligible"
        actual = parse_yes_no(row.get("human_evidence_eligible_label")) is True
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
        "v1_rows": len(v1), "evidence_judged": len(judged), "evidence_missing": len(v1) - len(judged),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "precision_denominator": tp + fp,
        "recall": tp / (tp + fn) if tp + fn else None,
        "recall_denominator": tp + fn,
        "v0": ranking["V0_Day1_Baseline"],
        "v1": ranking["V1_Optimized_Rules"],
    }
