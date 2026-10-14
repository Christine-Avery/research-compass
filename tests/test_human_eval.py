from research_compass.human_eval import calculate_metrics, row_key


def make_row(version, branch, rank, score="", evidence="", status="Retrieved", paper="same-paper"):
    return {
        "version": version, "branch": branch, "raw_rank": str(rank),
        "paper_id": paper, "human_relevance_label": score,
        "human_evidence_eligible_label": evidence, "rule_status": status,
        "title": f"Paper {rank}",
    }


def test_metrics_skip_incomplete_branches_and_report_denominators():
    rows = [make_row("V1_Optimized_Rules", "overview", i, score, "no", "Evidence Eligible") for i, score in enumerate([2, 1, 0, 0, 1], 1)]
    rows.extend(make_row("V1_Optimized_Rules", "methods", i, "" if i == 5 else 0, "", "Retrieved") for i in range(1, 6))
    metrics = calculate_metrics(rows)["versions"]["V1_Optimized_Rules"]
    assert metrics["complete_top_k_branches"] == 1
    assert metrics["precision_at_k"] == 3 / 5
    assert 0 < metrics["ndcg_at_k"] <= 1
    assert metrics["irrelevant_evidence_numerator"] == 2
    assert metrics["irrelevant_evidence_denominator"] == 5
    assert metrics["total_rows"] == 10


def test_v1_gate_audit_and_v0_gate_not_applicable():
    rows = [
        make_row("V1_Optimized_Rules", "target_method", 1, 0, "no", "Evidence Eligible", "a"),
        make_row("V1_Optimized_Rules", "target_method", 2, 2, "yes", "Retrieved", "b"),
        make_row("V1_Optimized_Rules", "target_method", 3, 1, "", "Retrieved", "c"),
        make_row("V0_Day1_Baseline", "overview", 1, 2, "yes", "Evidence Eligible", "d"),
    ]
    result = calculate_metrics(rows)["versions"]
    gate = result["V1_Optimized_Rules"]["evidence_gate"]
    assert gate["labeled_denominator"] == 2
    assert gate["false_accept_count"] == 1
    assert gate["false_reject_count"] == 1
    assert result["V0_Day1_Baseline"]["evidence_gate"] is None


def test_identical_paper_in_different_branches_has_distinct_review_id():
    paper_a = make_row("V0_Day1_Baseline", "overview", 1)
    paper_b = make_row("V0_Day1_Baseline", "methods", 1)
    assert row_key(paper_a, 0) != row_key(paper_b, 1)
