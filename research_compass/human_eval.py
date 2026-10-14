"""Pure helpers for human relevance and evidence-gate evaluation."""

from __future__ import annotations

from collections import defaultdict
from math import log2
from typing import Any, Iterable


def row_key(row: dict[str, Any], index: int) -> str:
    """Keep judgments independent for the same paper retrieved in different branches."""
    return "|".join(str(row.get(field, "")) for field in ("version", "branch", "raw_rank", "paper_id")) + f"|{index}"


def parse_relevance(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return score if score in (0, 1, 2) else None


def parse_yes_no(value: Any) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"yes", "是", "true", "1", "eligible"}:
        return True
    if normalized in {"no", "否", "false", "0", "ineligible"}:
        return False
    return None


def error_record(row: dict[str, Any]) -> dict[str, str]:
    return {key: str(row.get(source, "")) for key, source in (
        ("version", "version"), ("branch", "branch"), ("raw_rank", "raw_rank"),
        ("paper_id", "paper_id"), ("title", "title"),
    )}


def calculate_metrics(rows: Iterable[dict[str, Any]], k: int = 5) -> dict[str, Any]:
    """Calculate ranking metrics only on completely judged top-k branches.

    Relevant means score >= 1. nDCG uses graded gain 2**score - 1. Unjudged
    papers are excluded from ranking metrics rather than treated as irrelevant.
    """
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    row_list = list(rows)
    for row in row_list:
        grouped[(str(row.get("version", "")), str(row.get("branch", "")))].append(row)

    versions: dict[str, Any] = {}
    for version in sorted({key[0] for key in grouped}):
        p_values: list[float] = []
        ndcg_values: list[float] = []
        version_groups = [(branch, items) for (v, branch), items in grouped.items() if v == version]
        for _, items in version_groups:
            top = sorted(items, key=lambda r: int(r.get("raw_rank") or 10**9))[:k]
            labels = [parse_relevance(r.get("human_relevance_label")) for r in top]
            if not top or any(label is None for label in labels):
                continue
            p_values.append(sum(label >= 1 for label in labels) / k)
            gains = [2**label - 1 for label in labels]
            dcg = sum(gain / log2(rank + 2) for rank, gain in enumerate(gains))
            ideal = sorted(gains, reverse=True)
            idcg = sum(gain / log2(rank + 2) for rank, gain in enumerate(ideal))
            ndcg_values.append(dcg / idcg if idcg else 0.0)

        vrows = [r for r in row_list if str(r.get("version", "")) == version]
        system_admitted = [
            r for r in vrows
            if str(r.get("rule_status", "")).strip().lower() == "evidence eligible"
            and parse_relevance(r.get("human_relevance_label")) is not None
        ]
        irrelevant = sum(parse_relevance(r.get("human_relevance_label")) == 0 for r in system_admitted)
        result: dict[str, Any] = {
            "branch_count": len(version_groups),
            "complete_top_k_branches": len(p_values),
            "precision_at_k": sum(p_values) / len(p_values) if p_values else None,
            "ndcg_at_k": sum(ndcg_values) / len(ndcg_values) if ndcg_values else None,
            "irrelevant_evidence_rate": irrelevant / len(system_admitted) if system_admitted else None,
            "irrelevant_evidence_numerator": irrelevant,
            "irrelevant_evidence_denominator": len(system_admitted),
            "judged_relevance_rows": sum(parse_relevance(r.get("human_relevance_label")) is not None for r in vrows),
            "total_rows": len(vrows),
        }
        if version == "V1_Optimized_Rules":
            false_accepts, false_rejects = [], []
            for row in vrows:
                human = parse_yes_no(row.get("human_evidence_eligible_label"))
                if human is None:
                    continue
                system = str(row.get("rule_status", "")).strip().lower() == "evidence eligible"
                if system and not human:
                    false_accepts.append(error_record(row))
                elif not system and human:
                    false_rejects.append(error_record(row))
            result["evidence_gate"] = {
                "labeled_denominator": sum(parse_yes_no(r.get("human_evidence_eligible_label")) is not None for r in vrows),
                "false_accept_count": len(false_accepts), "false_reject_count": len(false_rejects),
                "false_accepts": false_accepts, "false_rejects": false_rejects,
            }
        else:
            result["evidence_gate"] = None
        versions[version] = result
    return {"k": k, "relevance_threshold": 1, "versions": versions}
