"""Read and validate the independent, human-curated Golden Case v2 snapshot."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "evaluation/cases/badcase_001/golden_case_v2.json"
RETRIEVAL_PATH = ROOT / "evaluation/runs/v3_20261014/live_openalex_golden.json"
ADJUDICATION_PATH = ROOT / "evaluation/freeze/final_20261014/final_adjudication.csv"
FORBIDDEN_PAPER_ID = "https://openalex.org/W1888026739"  # Pending NLP adjudication.


def load_golden_v2() -> list[dict]:
    """Return display-ready cards without changing any source or label file."""
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    if (snapshot.get("schema_version") != "golden_case_v2_human_curated_20261015"
            or snapshot.get("case_id") != "badcase_001"
            or snapshot.get("source_retrieval") != str(RETRIEVAL_PATH.relative_to(ROOT)).replace("\\", "/")
            or snapshot.get("source_adjudication") != str(ADJUDICATION_PATH.relative_to(ROOT)).replace("\\", "/")):
        raise ValueError("Golden Case v2 source declaration is invalid")

    retrieval = json.loads(RETRIEVAL_PATH.read_text(encoding="utf-8"))
    papers = {paper["id"]: paper for paper in retrieval["strategies"]["V1_Optimized_Rules"]["search"]["papers"]}
    with ADJUDICATION_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = {row["paper_id"]: row for row in csv.DictReader(handle)
                if row["version"] == "V1_Optimized_Rules"}

    cards = snapshot.get("cards")
    if not isinstance(cards, list) or [card.get("key") for card in cards] != ["A", "B", "C"]:
        raise ValueError("Golden Case v2 must contain the three reviewed cards")

    used_evidence: set[str] = set()
    for card in cards:
        for field in ("title", "evidence_maturity", "research_question", "transfer_hypothesis",
                      "next_action", "english_search_query"):
            if not isinstance(card.get(field), str) or not card[field].strip():
                raise ValueError(f"Golden Case v2 card {card['key']} has an empty {field}")
        query = card["english_search_query"]
        if not query.isascii() or len(query) > 360:
            raise ValueError("Golden Case v2 query must be bounded English text")
        if (not isinstance(card.get("evidence_gaps"), list) or not card["evidence_gaps"]
                or not all(isinstance(gap, str) and gap.strip() for gap in card["evidence_gaps"])):
            raise ValueError("Golden Case v2 requires explicit evidence gaps")
        evidence = card.get("evidence_backed_background")
        reading = card.get("further_reading")
        if not isinstance(evidence, list) or not evidence or not isinstance(reading, list):
            raise ValueError("Golden Case v2 must separate evidence from further reading")
        evidence_ids: set[str] = set()
        for item in evidence:
            paper_id = item.get("paper_id")
            paper, row = papers.get(paper_id), rows.get(paper_id)
            if (paper_id == FORBIDDEN_PAPER_ID or not paper or not row
                    or row["rule_status"] != "Evidence Eligible"
                    or row["human_evidence_eligible_label"] != "yes"
                    or row["adjudication_status"] == "pending_user_decision"
                    or row["title"].strip() != paper["title"].strip()
                    or row["abstract"].strip() != (paper.get("abstract") or "").strip()):
                raise ValueError(f"Golden Case v2 paper is not eligible evidence: {paper_id}")
            quote = item.get("quote")
            if (not isinstance(quote, str) or len(quote) < 25
                    or quote not in (paper.get("abstract") or "")
                    or not isinstance(item.get("claim"), str) or not item["claim"].strip()
                    or paper_id in evidence_ids):
                raise ValueError(f"Golden Case v2 claim lacks a unique abstract excerpt: {paper_id}")
            evidence_ids.add(paper_id)
            used_evidence.add(paper_id)
            item["paper_title"] = paper["title"]
            item["openalex_url"] = paper_id
            item["source_url"] = paper.get("source_url") or paper_id
            item["role"] = "NN source" if row["branch"] == "source_method" else "GP target"
        reading_ids: set[str] = set()
        for item in reading:
            paper_id = item.get("paper_id")
            paper, row = papers.get(paper_id), rows.get(paper_id)
            if (paper_id == FORBIDDEN_PAPER_ID or not paper or not row or paper_id in evidence_ids
                    or paper_id in reading_ids or row["human_evidence_eligible_label"] != "no"
                    or row["rule_status"] == "Evidence Eligible"
                    or not isinstance(item.get("reason"), str) or not item["reason"].strip()):
                raise ValueError(f"Golden Case v2 further reading is not excluded: {paper_id}")
            reading_ids.add(paper_id)
            item["paper_title"] = paper["title"]
            item["openalex_url"] = paper_id
            item["human_relevance_label"] = row["human_relevance_label"]
            item["human_evidence_eligible_label"] = row["human_evidence_eligible_label"]
    if len(used_evidence) != 5:
        raise ValueError("Golden Case v2 evidence set differs from the reviewed content")
    return cards
