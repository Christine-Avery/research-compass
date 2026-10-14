"""Reproducible offline replay of badcase_001; never edits its source files."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_compass.evidence import build_report
from research_compass.planning import normalize_concepts, normalize_domain, parse_intent, build_planned_branches
from research_compass.retrieval import Paper, SearchOutcome, QueryRecord, assess_relevance

CASE = ROOT / "evaluation" / "cases" / "badcase_001"
OUT = ROOT / "evaluation" / "runs" / "p0_20261014"
ORIGINAL = CASE / "original_trace.json"
EXPECTED = CASE / "expected_intent.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    original_hash = sha256(ORIGINAL)
    expected = load_json(EXPECTED)
    if original_hash != expected["source_trace_sha256"]:
        raise SystemExit("Golden trace hash mismatch; refusing replay")
    original = load_json(ORIGINAL)
    if not isinstance(original, dict):
        raise SystemExit("Golden trace is not a JSON object")

    start = perf_counter()
    text = original["interest"]
    parsed = parse_intent(text)
    v1_concepts = normalize_concepts(text)
    v1_domain = normalize_domain(text)
    v2_branches = build_planned_branches(parsed)
    v2_elapsed_ms = round((perf_counter() - start) * 1000, 3)

    # Keep the exact historic retrieval pool, in its historic branch/rank order.
    planned = original.get("planned", {}).get("search", {})
    baseline = original.get("baseline", {}).get("search", {})
    paper_by_id: dict[str, Paper] = {}
    old_query_by_id: dict[str, list[dict]] = {}
    for query in planned.get("queries", []):
        for hit in query.get("ranked_results", []):
            old_query_by_id.setdefault(hit["paper_id"], []).append({"branch_key": query["branch_key"], "raw_rank": hit.get("rank")})
    for paper_data in planned.get("papers", []):
        paper_by_id[paper_data["id"]] = Paper(
            paper_data["id"], paper_data.get("title", ""), paper_data.get("year"), paper_data.get("abstract"),
            paper_data.get("source_url"), paper_data.get("openalex_url"), paper_data.get("doi"),
            paper_data.get("found_by", []), paper_data.get("is_demo", False),
        )
    review_papers = dict(paper_by_id)
    for paper_data in baseline.get("papers", []):
        review_papers.setdefault(paper_data["id"], Paper(
            paper_data["id"], paper_data.get("title", ""), paper_data.get("year"), paper_data.get("abstract"),
            paper_data.get("source_url"), paper_data.get("openalex_url"), paper_data.get("doi"),
            paper_data.get("found_by", []), paper_data.get("is_demo", False),
        ))

    # V3 is explicitly a gate replay against the archived candidate pool. It is
    # not a new retrieval result, and no new rank or P@5 is inferred from it.
    v3_branches = []
    v3_queries = []
    for branch in v2_branches:
        hits = []
        for paper in paper_by_id.values():
            decision = assess_relevance(paper, branch, parsed)
            hits.append({"paper_id": paper.id, "historic_occurrences": old_query_by_id.get(paper.id, []), **decision})
        v3_branches.append({
            "branch": {"key": branch.key, "title": branch.title, "query": branch.query, "required_methods": branch.required_methods},
            "candidate_pool_source": "original_trace.json planned.search.papers",
            "candidate_pool_size": len(paper_by_id),
            "replayed_hits": hits,
            "evidence_eligible_ids": [hit["paper_id"] for hit in hits if hit["evidence_eligible"]],
        })
        ranked = [
            {"rank": None, "paper_id": paper.id, **assess_relevance(paper, branch, parsed)}
            for paper in paper_by_id.values()
        ]
        v3_queries.append(QueryRecord(branch.key, branch.query, [h["paper_id"] for h in ranked], ranked_results=ranked))
    replay_outcome = SearchOutcome("live" if paper_by_id else "demo", list(paper_by_id.values()), v3_queries, "offline_snapshot")
    report = build_report(replay_outcome, parsed, {branch.key: branch.title for branch in v2_branches})
    old_generation = original.get("planned", {}).get("generation") or {}
    legacy_claims = [*old_generation.get("current_work", []), *old_generation.get("explicit_limitations", [])]
    exact_spans = 0
    for claim in legacy_claims:
        source = paper_by_id.get(claim.get("paper_id"))
        if source and source.abstract and claim.get("quote") in source.abstract:
            exact_spans += 1

    replay = {
        "schema_version": "p0_snapshot_replay_v1",
        "case_id": "badcase_001",
        "source_files": {
            "original_trace.json": {"sha256": original_hash, "read_only": ORIGINAL.stat().st_file_attributes & 1 != 0},
            "expected_intent.json": {"sha256": sha256(EXPECTED), "read_only": EXPECTED.stat().st_file_attributes & 1 != 0},
        },
        "V0": {
            "description": "Archived rule-based planned result and generation, unchanged",
            "intent": original.get("intent"),
            "query_count": len(planned.get("queries", [])),
            "retrieved_unique_papers": len(paper_by_id),
            "generation": old_generation,
            "baseline": {
                "branch_count": len(original.get("baseline", {}).get("branches", [])),
                "queries": original.get("baseline", {}).get("search", {}).get("queries", []),
                "papers": original.get("baseline", {}).get("search", {}).get("papers", []),
                "generation": original.get("baseline", {}).get("generation"),
            },
        },
        "V1": {
            "description": "Cross-language term normalization only; roles and relation are not inferred",
            "normalized_domain": v1_domain,
            "normalized_concepts": list(v1_concepts),
        },
        "V2": {
            "description": "Structured intent and intent-specific dynamic query branches",
            "intent": parsed.to_dict(),
            "branches": [{"key": b.key, "title": b.title, "purpose": b.purpose, "query": b.query, "required_methods": list(b.required_methods)} for b in v2_branches],
            "offline_planning_latency_ms": v2_elapsed_ms,
        },
        "V3": {
            "description": "Relevance/evidence gate replay over archived V0 candidate pool; no new OpenAlex retrieval and no inferred ranking",
            "branches": v3_branches,
            "generation": report.to_dict() if report else None,
        },
        "mechanical_checks": {
            "legacy_quote_exact_span_count": exact_spans,
            "legacy_quote_count": len(legacy_claims),
            "interpretation": "Exact span presence verifies provenance only, not semantic relevance or whether the quote supports the generated claim.",
        },
    }
    write_json(OUT / "snapshot_replay.json", replay)

    # Metrics are explicitly null where the user's human relevance/claim labels
    # are needed. The CSV is a blinded-ready adjudication sheet, not prefilled by
    # the model being evaluated.
    gold_slots = 6
    v0_intent = original.get("intent", {})
    v0_slots = {
        "domain": False, "source_method": False, "target_method": False,
        "task": False, "relationship": False,
        "explicit_constraints": not bool(v0_intent.get("constraints")),
    }
    v1_slots = {"domain": v1_domain.startswith(expected["domain"]["name"]), "source_method": False, "target_method": False, "task": False, "relationship": False, "explicit_constraints": True}
    v2_slots = {
        "domain": parsed.domain.startswith(expected["domain"]["name"]),
        "source_method": parsed.source_method == expected["idea_transfer"]["from"],
        "target_method": parsed.target_method == expected["idea_transfer"]["to"],
        "task": parsed.task == "方法比较与研究思路迁移",
        "relationship": parsed.relationship == "Neural Networks → Gaussian Processes",
        "explicit_constraints": not parsed.explicit_constraints,
    }
    intent_results = {}
    for name, slots in (("V0", v0_slots), ("V1", v1_slots), ("V2", v2_slots), ("V3", v2_slots)):
        matches = sum(bool(v) for v in slots.values())
        intent_results[name] = {"matches": matches, "denominator": gold_slots, "score": round(matches / gold_slots, 4), "slots": slots, "n_cases": 1}

    metrics = {
        "schema_version": "p0_metrics_v1",
        "sample": {"golden_cases": 1, "other_multilingual_cases": 2, "other_case_status": "unit-test assertions only; not human-adjudicated metric sample"},
        "metric_definitions": {
            "Intent Preservation": "exactly matched gold slots / 6 per case: domain, source method, target method, task, direction, explicit constraints; aggregate case-level mean.",
            "Precision@5": "human-labeled relevant works among first 5 original-ranked works / 5 per branch; not scored until adjudication file is completed.",
            "Direction Coverage": "gold directions with >=1 human-labeled relevant result / number of gold directions; result must be tied to actual branch retrieval.",
            "Irrelevant Evidence Rate": "human-labeled irrelevant works used by landscape/factual claims/RQs / all works used by those outputs; undefined with zero outputs.",
            "Claim Support Rate": "human-adjudicated supported factual claims / all factual claims; exact quote substring is reported separately and is not substituted for semantic support.",
            "Latency": "wall-clock milliseconds for recorded local planning/retrieval/generation stages; historic V0 latency unavailable; offline replay latency excludes API.",
            "Cost": "actual billed LLM cost; no LLM calls in this run, so $0. OpenAlex free API cost is $0; limits/rate caps still apply.",
        },
        "Intent Preservation": intent_results,
        "Precision@5": {"result": None, "reason": "human relevance labels pending", "denominator": "5 per branch with results; see human_review.csv"},
        "Direction Coverage": {"result": None, "reason": "snapshot replay is not fresh branch retrieval; manual review plus real retrieval required"},
        "Irrelevant Evidence Rate": {"result": None, "reason": "semantic human labels pending"},
        "Claim Support Rate": {"result": None, "reason": "semantic support labels pending", "mechanical_exact_span": {"numerator": exact_spans, "denominator": len(legacy_claims)} if legacy_claims else None},
        "latency_ms": {"V0": None, "V1": None, "V2_planning": v2_elapsed_ms, "V3_offline_gate_included_in_total": True},
        "cost_usd": {"llm": 0, "openalex": 0},
        "gate_replay": {"candidate_pool_size": len(paper_by_id), "evidence_eligible_ids_by_branch": {b["branch"]["key"]: b["evidence_eligible_ids"] for b in v3_branches}},
    }
    write_json(OUT / "metrics.json", metrics)

    fields = ["case_id", "paper_id", "title", "historic_branches", "historic_ranks", "relevance_label", "evidence_eligible_label", "claim_support_label", "reviewer", "notes"]
    with (OUT / "human_review.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for paper in review_papers.values():
            occ = old_query_by_id.get(paper.id, [])
            baseline_occ = []
            for query in baseline.get("queries", []):
                for hit in query.get("ranked_results", []):
                    if hit.get("paper_id") == paper.id:
                        baseline_occ.append({"branch_key": query["branch_key"], "raw_rank": hit.get("rank")})
            occ.extend(baseline_occ)
            writer.writerow({
                "case_id": "badcase_001", "paper_id": paper.id, "title": paper.title,
                "historic_branches": ";".join(dict.fromkeys(o["branch_key"] for o in occ)),
                "historic_ranks": ";".join(f"{o['branch_key']}#{o.get('raw_rank')}" for o in occ),
                "relevance_label": "", "evidence_eligible_label": "", "claim_support_label": "", "reviewer": "", "notes": "",
            })
    print(json.dumps({"source_hash": original_hash, "V0_candidate_papers": len(paper_by_id), "V3_eligible_by_branch": {b["branch"]["key"]: len(b["evidence_eligible_ids"]) for b in v3_branches}, "Intent_Preservation": {k: v["score"] for k, v in intent_results.items()}, "output_dir": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
