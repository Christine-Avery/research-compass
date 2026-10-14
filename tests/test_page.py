from dataclasses import dataclass
from pathlib import Path

from streamlit.testing.v1 import AppTest

from research_compass.evidence import ExplorationReport
from research_compass.exploration import SearchBranch
from research_compass.planning import ResearchIntent
from research_compass.retrieval import Paper, QueryRecord, SearchOutcome


@dataclass
class LegacyLandscapeRow:
    branch_key: str
    branch_title: str
    paper_ids: list[str]


def test_page_renders_landscape_from_legacy_session_row():
    paper = Paper(
        "https://openalex.org/W123", "Relevant robot paper", 2024,
        "This paper presents a robot control method with sufficient abstract text for display.",
        "https://doi.org/10.1234/example", "https://openalex.org/W123", None,
        found_by=["techniques"],
    )
    outcome = SearchOutcome(
        "live", [paper],
        [QueryRecord("techniques", "robot control", [paper.id])], "now",
    )
    report = ExplorationReport(
        "extractive_rules_v1", "Test scope",
        [LegacyLandscapeRow("techniques", "技术路线", [paper.id])], [], [], [],
    )
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    app.switch_page("pages/1_Home.py").run()
    app.session_state.stage = "results"
    app.session_state.interest = "robot control"
    app.session_state.intent = ResearchIntent("robot control", "robot control", "AI", "map")
    app.session_state.planned_outcome = outcome
    app.session_state.baseline_outcome = outcome
    app.session_state.report = report
    app.session_state.selected_branches = [SearchBranch("techniques", "技术路线", "", "robot control")]
    app.run(timeout=10)
    assert not app.exception
    assert any("初步研究版图" in item.value for item in app.subheader)
    assert any("Relevant robot paper" in item.value for item in app.caption)
