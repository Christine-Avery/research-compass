"""The curated demonstration is separate from retrieval and frozen evaluation."""

import hashlib
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from research_compass.golden_v2 import SNAPSHOT_PATH, load_golden_v2, load_golden_v2_path
from research_compass.prototype_snapshot import load_golden_snapshot
from research_compass.retrieval import QueryRecord, SearchOutcome


ROOT = Path(__file__).parents[1]


def test_v2_cards_have_reviewed_evidence_and_separate_rejected_reading():
    cards = load_golden_v2()
    assert [card["key"] for card in cards] == ["A", "B", "C"]
    assert [len(card["evidence_backed_background"]) for card in cards] == [3, 1, 1]
    assert [len(card["further_reading"]) for card in cards] == [0, 1, 2]
    assert {item["paper_id"] for card in cards for item in card["evidence_backed_background"]} == {
        "https://openalex.org/W2406620654", "https://openalex.org/W2298163601",
        "https://openalex.org/W4295046714", "https://openalex.org/W2018705428",
        "https://openalex.org/W2156562940",
    }
    assert all("待验证" in card["transfer_hypothesis"] for card in cards)
    assert all(card["english_search_query"].isascii() for card in cards)
    assert "https://openalex.org/W1888026739" not in SNAPSHOT_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize("paper_id", [
    "https://openalex.org/W2798274031",
    "https://openalex.org/W1545951971",
    "https://openalex.org/W2913473169",
])
def test_rejected_paper_cannot_be_promoted_to_background(tmp_path, monkeypatch, paper_id):
    import research_compass.golden_v2 as module

    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    snapshot["cards"][0]["evidence_backed_background"][0]["paper_id"] = paper_id
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(module, "SNAPSHOT_PATH", altered)
    with pytest.raises(ValueError, match="not eligible evidence"):
        module.load_golden_v2()


def test_unsupported_excerpt_cannot_be_displayed_as_background(tmp_path, monkeypatch):
    import research_compass.golden_v2 as module

    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    snapshot["cards"][0]["evidence_backed_background"][0]["quote"] = "This unsupported sentence is not in the archived abstract."
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(module, "SNAPSHOT_PATH", altered)
    with pytest.raises(ValueError, match="lacks a unique abstract excerpt"):
        module.load_golden_v2()


def test_frozen_trace_labels_and_adjudication_content_hashes():
    expected_raw = {
        "evaluation/cases/badcase_001/original_trace.json": "42245808de0b10663652a8d2f28cd27458e4a7aba00c57d78134586e7ef09658",
        "evaluation/runs/v3_20261014/human_labels.csv": "00168b25e1c614bb9a53b6349a99bb177f145adcf16354b989322e7fe770b0aa",
    }
    for path, digest in expected_raw.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    # Git may normalize the adjudication CSV's CRLF on Linux; its records stay identical.
    adjudication = (ROOT / "evaluation/freeze/final_20261014/final_adjudication.csv").read_bytes()
    assert hashlib.sha256(adjudication.replace(b"\r\n", b"\n")).hexdigest() == (
        "6f0e46badd06d3c64c01aaf8024c84d3dbbe8a35abefc4cbbbab82aec81e42be"
    )


def test_v2_path_ids_map_to_reviewed_cards():
    expected = {"uncertainty_comparison": "A", "architecture_insights": "C",
                "hybrid_control_strategies": "B"}
    for path_id, card_id in expected.items():
        mapping, card = load_golden_v2_path(path_id)
        assert mapping["card_id"] == card_id == card["key"]
        assert mapping["progression"]


def test_v2_single_card_path_switch_and_query_uses_existing_live_search(monkeypatch):
    import research_compass.retrieval as retrieval
    import research_compass.qwen_planning as qwen

    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "true")
    monkeypatch.setenv("PUBLIC_QWEN_ENABLED", "false")
    monkeypatch.setenv("PUBLIC_QWEN_SECURITY_REVIEW_PASSED", "false")
    monkeypatch.setattr(qwen, "plan_with_qwen", lambda *a, **k: pytest.fail("No Qwen call allowed"))
    searches = []

    def fake_search(branches, key, *, intent):
        searches.append(branches[0].query)
        return SearchOutcome("live", [], [QueryRecord(branches[0].key, branches[0].query, [])], "test-time")

    monkeypatch.setattr(retrieval, "search_papers", fake_search)
    intent, branches, _, outcomes = load_golden_snapshot()
    selected = branches[0].key
    outcome, report = outcomes[selected]
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
    app.session_state.confirmed_intent = intent
    app.session_state.draft_paths = branches
    app.session_state.selected_path = selected
    app.session_state.selected_path_id = selected
    app.session_state.selected_outcome = outcome
    app.session_state.selected_report = report
    app.session_state.path_outcomes = outcomes
    app.session_state._prototype_snapshot_loaded = True
    app.session_state.golden_v2_mode = True
    app.switch_page("pages/3_Evidence_Next.py").run()
    assert not app.exception
    assert any("研究方向 · 稳定性与安全验证" in item.value for item in app.markdown)
    assert sum("研究方向 · " in item.value for item in app.markdown) == 1
    assert searches == []

    for next_index, expected_title in [(1, "NN 结构与 GP 表达能力"), (2, "在线学习与 GP 模型更新")]:
        app.switch_page("pages/2_Path_Explorer.py").run()
        next(button for button in app.button if button.key == f"choose_{next_index + 1}").click().run()
        app.switch_page("pages/2_Path_Explorer.py").run()
        assert app.session_state.selected_path_id == branches[next_index].key
        next(button for button in app.button if button.label == "形成下一步研究计划").click().run()
        app.switch_page("pages/3_Evidence_Next.py").run()
        assert not app.exception
        assert any(f"研究方向 · {expected_title}" in item.value for item in app.markdown)
        assert sum("研究方向 · " in item.value for item in app.markdown) == 1
        assert searches == []

    query = "neural network online learning gaussian process model update control"
    next(field for field in app.text_input if field.key == "golden_v2_query_hybrid_control_strategies").set_value(query).run()
    next(button for button in app.button if button.label == "继续检索").click().run()
    assert not app.exception
    assert app.session_state.next_query_draft == query
    assert app.session_state.golden_v2_next_card == "B"
    assert any("Research Path Explorer" in title.value for title in app.title)
    assert searches == []  # Opening Page 2 does not automatically search.
    app.switch_page("pages/2_Path_Explorer.py").run()
    next(button for button in app.button if button.label == "按此检索式执行 OpenAlex 检索").click().run()
    assert not app.exception
    assert searches == [query]
    assert app.session_state.selected_outcome.mode == "live"
    assert app.session_state.get("golden_v2_next_card") is None
    app.switch_page("pages/3_Evidence_Next.py").run()
    assert not app.exception
    assert not any("研究方向 · " in item.value for item in app.markdown)
