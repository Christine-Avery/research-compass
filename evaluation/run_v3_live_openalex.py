"""Fetch current Golden Case results without touching the frozen trace."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from research_compass.evidence import build_report
from research_compass.exploration import SearchBranch
from research_compass.planning import build_planned_branches, parse_intent
from research_compass.retrieval import search_papers

TRACE = ROOT / "evaluation" / "cases" / "badcase_001" / "original_trace.json"
EXPECTED = ROOT / "evaluation" / "cases" / "badcase_001" / "expected_intent.json"
OUT = ROOT / "evaluation" / "runs" / "v3_20261014"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def branch_from_saved(item: dict) -> SearchBranch:
    return SearchBranch(
        key=str(item.get("key", "baseline")), title=str(item.get("title", "Day 1 Baseline")),
        purpose=str(item.get("purpose", "")), query=str(item.get("query", "")),
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    trace_hash = digest(TRACE)
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    if trace_hash != expected["source_trace_sha256"]:
        raise SystemExit("Golden trace hash mismatch; refusing Live run")
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    key = os.getenv("OPENALEX_API_KEY")
    print(json.dumps({"openalex_api_key_loaded": bool(key), "trace_hash_verified": True}, ensure_ascii=False))
    v0_started = perf_counter()
    legacy_branches = [branch_from_saved(item) for item in trace.get("baseline", {}).get("branches", [])]
    outcomes = {
        "V0_Day1_Baseline": search_papers(legacy_branches, key, per_branch=5, intent=None),
    }
    v0_elapsed_ms = round((perf_counter() - v0_started) * 1000, 2)
    v1_started = perf_counter()
    intent = parse_intent(trace["interest"])
    rules_branches = build_planned_branches(intent)
    outcomes["V1_Optimized_Rules"] = search_papers(rules_branches, key, per_branch=5, intent=intent)
    v1_elapsed_ms = round((perf_counter() - v1_started) * 1000, 2)

    # API key status is the only credential-related output. Search results are
    # a new run artifact; the original trace remains unchanged.
    payload = {
        "schema_version": "v3_live_openalex_golden_v1",
        "case_id": "badcase_001",
        "source_trace_sha256": trace_hash,
        "openalex_api_key_loaded": bool(key),
        "note": "Only this newly executed run is Live; demo fallback is explicitly reported by its mode.",
        "strategies": {},
    }
    print_view = {"trace_hash_verified": True, "strategies": {}}
    review_rows = []
    for version, outcome in outcomes.items():
        report = build_report(outcome, intent, {b.key: b.title for b in legacy_branches + rules_branches}) if version.startswith("V1") else None
        serialized = outcome.to_dict()
        payload["strategies"][version] = {
            "retrieval_mode": outcome.mode, "retrieved_at": outcome.retrieved_at,
            "notice": outcome.notice, "search": serialized,
            "evidence_report": report.to_dict() if report else None,
            "end_to_end_ms": v0_elapsed_ms if version.startswith("V0") else v1_elapsed_ms,
        }
        by_id = {paper.id: paper for paper in outcome.papers}
        branch_view = []
        for record in outcome.queries:
            hits = []
            for hit in record.ranked_results[:5]:
                paper = by_id.get(hit.get("paper_id"))
                if paper:
                    if int(hit.get("raw_rank") or 99) <= 2:
                        hits.append({
                            "raw_rank": hit.get("raw_rank"), "relevance_rank": hit.get("relevance_rank"),
                            "paper_id": paper.id, "title": paper.title, "year": paper.year,
                            "abstract": paper.abstract, "source_url": paper.source_url,
                            "openalex_url": paper.openalex_url, "status": hit.get("status"),
                            "reason": hit.get("reason"),
                        })
                    review_rows.append({
                        "version": version, "branch": record.branch_key, "raw_rank": hit.get("raw_rank"),
                        "relevance_rank": hit.get("relevance_rank"), "paper_id": paper.id,
                        "doi": paper.doi or "", "title": paper.title, "abstract": paper.abstract or "",
                        "rule_status": hit.get("status", "Retrieved"), "human_relevance_label": "",
                        "human_evidence_eligible_label": "", "claim_support_label": "", "reviewer": "", "notes": "",
                    })
            branch_view.append({"branch": record.branch_key, "query": record.query, "error": record.error, "top_hits": hits})
        print_view["strategies"][version] = {
            "mode": outcome.mode, "notice": outcome.notice,
            "end_to_end_ms": v0_elapsed_ms if version.startswith("V0") else v1_elapsed_ms,
            "paper_count": len(outcome.papers), "branch_results": branch_view,
            "evidence_eligible": sum(bool(hit.get("evidence_eligible")) for rec in outcome.queries for hit in rec.ranked_results),
        }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "live_openalex_golden.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    import csv
    review_path = OUT / "live_openalex_human_review.csv"
    headers = list(review_rows[0]) if review_rows else ["version", "branch", "raw_rank", "paper_id", "title", "human_relevance_label", "human_evidence_eligible_label", "reviewer", "notes"]
    with review_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(review_rows)
    print_view["artifact"] = str(OUT / "live_openalex_golden.json")
    print_view["manual_review_rows"] = len(review_rows)
    print(json.dumps(print_view, ensure_ascii=False))


if __name__ == "__main__":
    main()
