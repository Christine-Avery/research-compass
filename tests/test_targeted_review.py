import csv
from hashlib import sha256
from pathlib import Path
import pytest

from research_compass.targeted_report import write_report
from research_compass.targeted_review import (
    EDIT_FIELDS, candidates, gate_metrics, load_reviewed, save_review, snapshot_rows,
)


ROOT = Path(__file__).parents[1]
SNAPSHOT = ROOT / "evaluation" / "runs" / "v3_20261014" / "human_labels.csv"


def test_targeted_review_writes_separate_labels_and_replays_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "false")
    original_hash = sha256(SNAPSHOT.read_bytes()).hexdigest()
    baseline = snapshot_rows(SNAPSHOT)
    selected = candidates(baseline)
    assert len(baseline) == 35
    assert len(selected) == 7
    conflicts = [row for row in baseline if row["review_id"] in {rid for rid, _ in selected}
                 and row["human_relevance_label"] == "0" and row["human_evidence_eligible_label"] == "yes"]
    assert len(conflicts) == 2
    row = conflicts[0]
    before = {field: row.get(field, "") for field in EDIT_FIELDS}
    after = dict(before, human_evidence_eligible_label="no")
    output = tmp_path / "human_labels_reviewed.csv"
    event = save_review(SNAPSHOT, tmp_path / "changes", output, row["review_id"], before, after, "Test-only human correction")
    assert event["before"]["human_evidence_eligible_label"] == "yes"
    assert event["after"]["human_evidence_eligible_label"] == "no"
    assert event["change_reason"] == "Test-only human correction"
    assert event["timestamp_utc"]
    assert sha256(SNAPSHOT.read_bytes()).hexdigest() == original_hash
    revised, reviewed = load_reviewed(SNAPSHOT, tmp_path / "changes")
    assert row["review_id"] in reviewed
    assert len(revised) == 35
    assert gate_metrics(revised)["fn"] == gate_metrics(baseline)["fn"] - 1
    with output.open(encoding="utf-8-sig", newline="") as handle:
        saved = list(csv.DictReader(handle))
    assert len(saved) == 35
    assert next(item for item in saved if item["review_id"] == row["review_id"])["human_evidence_eligible_label"] == "no"
    report = write_report(SNAPSHOT, tmp_path)
    assert report["status"] == "pending_human_review"
    assert report["reviewed_candidate_count"] == 1


def test_missing_human_reason_cannot_change_labels(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "false")
    row = snapshot_rows(SNAPSHOT)[-1]
    before = {field: row.get(field, "") for field in EDIT_FIELDS}
    try:
        save_review(SNAPSHOT, tmp_path / "changes", tmp_path / "reviewed.csv", row["review_id"], before, before, "")
    except ValueError as exc:
        assert "reason" in str(exc)
    else:
        raise AssertionError("A review without a human reason was saved")
    assert not (tmp_path / "changes").exists()


def test_public_deployment_refuses_targeted_annotation_write(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "true")
    row = snapshot_rows(SNAPSHOT)[0]
    before = {field: row.get(field, "") for field in EDIT_FIELDS}
    with pytest.raises(PermissionError, match="read-only"):
        save_review(SNAPSHOT, tmp_path / "changes", tmp_path / "reviewed.csv", row["review_id"], before, before, "No write in public mode")
    assert not (tmp_path / "changes").exists()
    assert not (tmp_path / "reviewed.csv").exists()
