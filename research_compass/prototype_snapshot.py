"""Explicit, read-only loader for historical Golden Case prototype screenshots."""

import json
from pathlib import Path

from research_compass.exploration import SearchBranch
from research_compass.planning import ResearchIntent
from research_compass.retrieval import Paper, QueryRecord, SearchOutcome


ROOT = Path(__file__).resolve().parents[1]
QWEN_PATH = ROOT / "evaluation/runs/v3_20261014/golden_qwen_live_20261014.json"
OPENALEX_PATH = ROOT / "evaluation/runs/v3_20261014/live_openalex_golden.json"


def load_golden_snapshot() -> tuple[ResearchIntent, list[SearchBranch], dict, dict[str, tuple[SearchOutcome, object]]]:
    """Load recorded Qwen planning and OpenAlex V1 data without network calls."""
    qwen = json.loads(QWEN_PATH.read_text(encoding="utf-8"))
    run = json.loads(OPENALEX_PATH.read_text(encoding="utf-8"))
    raw_intent = qwen["intent"]
    tuple_fields = {"explicit_constraints", "inferred", "unconfirmed", "concepts"}
    intent_data = {key: (tuple(value) if key in tuple_fields else value)
                   for key, value in raw_intent.items()}
    intent = ResearchIntent(**intent_data)
    branches = [SearchBranch(**{
        key: (tuple(value) if key in {"required_methods", "query_aliases"} else value)
        for key, value in item.items()
    }) for item in qwen["branches"]]
    metadata = qwen["metadata"]

    saved_search = run["strategies"]["V1_Optimized_Rules"]["search"]
    all_papers = {item["id"]: Paper(**item) for item in saved_search["papers"]}
    outcomes: dict[str, tuple[SearchOutcome, object]] = {}
    record_map = {item["branch_key"]: item for item in saved_search["queries"]}
    # Qwen's three dynamic routes correspond to the archived target/comparison
    # retrievals. Keep the exact API query and raw ordering in the saved result.
    sources = ["target_method", "source_method", "comparison_transfer"]
    for branch, source_key in zip(branches, sources):
        record = record_map.get(source_key)
        if not record:
            continue
        query_record = QueryRecord(**{**record, "branch_key": branch.key})
        ids = set(record["returned_ids"])
        papers = [paper for paper_id, paper in all_papers.items() if paper_id in ids]
        outcome = SearchOutcome(
            mode="snapshot", papers=papers, queries=[query_record],
            retrieved_at=saved_search["retrieved_at"],
            notice="Historical OpenAlex result snapshot paired for prototype review; no live request was made.",
        )
        from research_compass.evidence import build_report
        report = build_report(outcome, intent, {branch.key: branch.title})
        outcomes[branch.key] = (outcome, report)
    return intent, branches, metadata, outcomes


def activate_golden_snapshot(step: int) -> None:
    """Seed a page from a clearly requested, read-only prototype URL fixture."""
    import streamlit as st

    if st.query_params.get("prototype_snapshot") != "golden" or st.session_state.get("_prototype_snapshot_loaded"):
        return
    intent, branches, metadata, outcomes = load_golden_snapshot()
    selected = st.query_params.get("path", branches[0].key if branches else "")
    st.session_state.interest = intent.original_interest
    st.session_state.draft_intent = intent
    st.session_state.draft_paths = branches
    st.session_state.plan_source = "qwen_snapshot"
    st.session_state.plan_meta = metadata
    st.session_state.plan_notice = "Historical snapshot loaded from saved files; no API request was made."
    st.session_state.path_outcomes = outcomes
    st.session_state._prototype_snapshot_loaded = True
    if st.query_params.get("opportunities") == "v2":
        st.session_state.golden_v2_mode = True
    if step >= 2:
        st.session_state.confirmed_intent = intent
        st.session_state.paths_confirmed = True
        st.session_state.selected_path = selected
        st.session_state.selected_path_id = selected
        cached = outcomes.get(selected)
        if cached:
            st.session_state.selected_outcome, st.session_state.selected_report = cached
    st.rerun()
