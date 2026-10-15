from evaluation.llm_vs_rules_v1.audit_recalculate import calculate


def test_independent_recalculation_matches_frozen_summary():
    report = calculate()
    assert report["frozen_set"]["sha256"] == "dfb37d8b2dd98a93e13c18e9f225d5ae8952def2d285e018b56407ae26a4ba6c"
    assert report["coverage"]["paired_n"] == 11
    assert report["metrics_consistency"]["all_passed"] is True
    assert report["metrics"]["A"]["mean_precision_at_5"] == 0.6363636363636364
    assert report["metrics"]["B"]["mean_precision_at_5"] == 0.8363636363636364
    assert abs(report["metrics"]["delta_ndcg_at_5"] - 0.18792878871159824) < 1e-12


def test_labels_and_top5_paper_ids_are_complete_and_provisional():
    report = calculate()
    assert report["labels"]["rows"] == 119
    assert report["labels"]["duplicate_query_paper_keys"] == 0
    assert report["labels"]["human_review_status_counts"] == {"pending": 119}
    assert report["integrity"]["missing_labels_for_top5"] == []
    assert report["integrity"]["top5_id_request_mismatches"] == []
    assert report["provenance_audit"]["qwen_ledger_attempts"] == 32
    assert report["provenance_audit"]["automatic_retries"] == 0
    assert report["provenance_audit"]["historic_ledger_hash_before_after_equal"] is True
    assert report["provenance_audit"]["all_unchanged_raw_artifact_hashes_match"] is True


def test_s4_has_no_complete_pairs_and_five_cases_are_unpaired():
    report = calculate()
    assert report["coverage"]["unpaired_ids"] == ["S2-02", "S4-01", "S4-02", "S4-03", "S4-04"]
    assert report["coverage"]["S4_paired_n"] == 0
