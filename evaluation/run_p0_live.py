"""One explicit real OpenAlex run for the P0 fixed-case query plan."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from research_compass.planning import build_planned_branches, parse_intent
from research_compass.retrieval import search_papers

OUT = ROOT / "evaluation" / "runs" / "p0_20261014" / "live_openalex.json"


def main() -> None:
    trace_path = ROOT / "evaluation" / "cases" / "badcase_001" / "original_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    # Print only a boolean about credential availability. Never log its value.
    key = os.getenv("OPENALEX_API_KEY")
    print(json.dumps({"openalex_api_key_loaded": bool(key)}, ensure_ascii=False))
    intent = parse_intent(trace["interest"])
    branches = build_planned_branches(intent)
    outcome = search_papers(branches, key, per_branch=5, intent=intent)
    payload = {
        "schema_version": "p0_live_openalex_v1",
        "input_case": "badcase_001",
        "api_key_loaded": bool(key),
        "retrieval_mode": outcome.mode,
        "retrieved_at": outcome.retrieved_at,
        "notice": outcome.notice,
        "intent": intent.to_dict(),
        "branches": [{"key": b.key, "title": b.title, "query": b.query, "focus_method": b.focus_method, "required_methods": list(b.required_methods), "query_aliases": list(b.query_aliases)} for b in branches],
        "search": outcome.to_dict(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    view = []
    by_id = {p.id: p for p in outcome.papers}
    for query in outcome.queries:
        view.append({
            "branch": query.branch_key,
            "query": query.query,
            "error": query.error,
            "hits": [
                {"raw_rank": hit.get("raw_rank"), "paper_id": hit.get("paper_id"), "status": hit.get("status"), "reason": hit.get("reason"), "title": by_id[hit["paper_id"]].title if hit.get("paper_id") in by_id else None, "year": by_id[hit["paper_id"]].year if hit.get("paper_id") in by_id else None, "source_url": by_id[hit["paper_id"]].source_url if hit.get("paper_id") in by_id else None}
                for hit in query.ranked_results
            ],
        })
    print(json.dumps({"retrieval_mode": outcome.mode, "notice": outcome.notice, "unique_paper_count": len(outcome.papers), "branch_results": view, "artifact": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
