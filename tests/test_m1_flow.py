"""M1 route and failure-state checks; all model and search calls are offline fakes."""

from pathlib import Path
import json

import pytest
from streamlit.testing.v1 import AppTest

from research_compass.evidence import build_report
from research_compass.planning import build_planned_branches, parse_intent
from research_compass.qwen_planning import QwenPlanningError, validate_plan
from research_compass.retrieval import Paper, QueryRecord, SearchOutcome


ROOT = Path(__file__).parents[1]


def _app():
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()


def _button(app, label):
    return next(button for button in app.button if button.label == label)


def test_ordinary_rule_query_reaches_path_cards_without_forced_question():
    app = _app()
    app.text_area[0].set_value("What are reinforcement learning methods in robot control?")
    app.radio[0].set_value("本地规则 V1")
    _button(app, "理解研究意图").click().run()
    assert not app.exception
    assert not any("关键歧义" in item.value for item in app.warning)
    _button(app, "确认意图，查看研究路径").click().run()
    assert not app.exception
    assert any("Research Path Explorer" in title.value for title in app.title)
    assert app.session_state.confirmed_intent.domain == "Control Theory / Control Systems"


@pytest.mark.parametrize(("path_number", "expected_path_id", "expected_card_id"), [
    (1, "uncertainty_comparison", "A"),
    (2, "architecture_insights", "C"),
    (3, "hybrid_control_strategies", "B"),
])
def test_page1_golden_snapshot_action_enters_single_card_v2_without_network(path_number, expected_path_id, expected_card_id, monkeypatch):
    """The explicit saved-snapshot button carries v2 state through normal navigation."""
    import research_compass.qwen_planning as qwen
    import research_compass.retrieval as retrieval
    from research_compass.golden_v2 import load_golden_v2_path

    monkeypatch.setattr(qwen, "plan_with_qwen", lambda *a, **k: pytest.fail("No Qwen call allowed"))
    monkeypatch.setattr(retrieval, "search_papers", lambda *a, **k: pytest.fail("No OpenAlex call allowed"))
    app = _app()
    next(button for button in app.button if "Golden Case" in button.label).click().run()
    assert not app.exception
    assert app.session_state._prototype_snapshot_loaded is True
    assert app.session_state.golden_v2_mode is True

    # The final Page 1 button is the explicit intent confirmation.
    app.button[-1].click().run()
    assert not app.exception
    app.switch_page("pages/2_Path_Explorer.py").run()
    next(button for button in app.button if button.key == f"choose_{path_number}").click().run()
    app.switch_page("pages/2_Path_Explorer.py").run()
    assert not app.exception
    app.button[-1].click().run()  # Form the next-step plan for that selected path.
    assert not app.exception
    app.switch_page("pages/3_Evidence_Next.py").run()
    assert not app.exception

    assert app.session_state.selected_path_id == expected_path_id
    mapping, card = load_golden_v2_path(app.session_state.selected_path_id)
    assert mapping["card_id"] == expected_card_id
    assert card["key"] == expected_card_id
    heading = f"### 研究方向 · {card['title']}"
    assert sum(heading in item.value for item in app.markdown) == 1
    assert app.session_state.selected_path_id == mapping["path_id"]
    assert app.session_state.selected_outcome.mode == "snapshot"



def test_key_ambiguity_asks_at_most_once_and_can_skip():
    app = _app()
    app.text_area[0].set_value("我想研究一种新的机器学习方法")
    app.radio[0].set_value("本地规则 V1")
    _button(app, "理解研究意图").click().run()
    assert not app.exception
    assert sum("关键歧义" in item.value for item in app.warning) == 1
    _button(app, "跳过").click().run()
    assert not app.exception
    assert not any("关键歧义" in item.value for item in app.warning)
    assert app.session_state.clarification_seen


def test_qwen_failure_is_labeled_rule_fallback(monkeypatch):
    import research_compass.qwen_planning as qwen

    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "false")

    def offline_failure(*args, **kwargs):
        raise QwenPlanningError("离线故障注入")

    monkeypatch.setattr(qwen, "plan_with_qwen", offline_failure)
    app = _app()
    app.text_area[0].set_value("Compare neural networks and Gaussian processes in control theory")
    app.radio[0].set_value("Qwen AI")
    _button(app, "理解研究意图").click().run()
    assert not app.exception
    assert app.session_state.plan_source == "rules_fallback"
    assert any("本地规则结果" in item.value for item in app.warning)


@pytest.mark.parametrize(("enabled", "review_passed"), [
    ("false", "false"), ("true", "false"), ("false", "true"),
])
def test_public_qwen_off_defaults_to_rules_and_never_reads_dev_ledger_or_calls_model(
    monkeypatch, enabled, review_passed,
):
    import research_compass.qwen_planning as qwen

    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "true")
    monkeypatch.setenv("PUBLIC_QWEN_ENABLED", enabled)
    monkeypatch.setenv("PUBLIC_QWEN_SECURITY_REVIEW_PASSED", review_passed)

    class ForbiddenLedger:
        def read_text(self, *args, **kwargs):
            raise AssertionError("Public page must not read the development ledger")

    model_calls = []

    def forbidden_model_call(*args, **kwargs):
        model_calls.append((args, kwargs))
        raise AssertionError("Disabled public Qwen must not be called")

    monkeypatch.setattr(qwen, "LEDGER", ForbiddenLedger())
    monkeypatch.setattr(qwen, "plan_with_qwen", forbidden_model_call)
    app = _app()
    assert not app.exception
    assert app.radio[0].value == "本地规则 V1"
    assert any("实时 AI 暂未开放" in item.value for item in app.info)
    assert not any("账本" in item.value for item in app.warning)

    app.text_area[0].set_value("Compare neural networks and Gaussian processes in control theory")
    app.radio[0].set_value("Qwen AI")
    _button(app, "理解研究意图").click().run()
    assert not app.exception
    assert model_calls == []
    assert app.session_state.plan_source == "rules_fallback"
    assert any("没有调用 Qwen" in item.value for item in app.warning)


def test_public_page_never_reads_development_ledger_even_when_switches_are_on(monkeypatch):
    import research_compass.qwen_planning as qwen

    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "true")
    monkeypatch.setenv("PUBLIC_QWEN_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_QWEN_SECURITY_REVIEW_PASSED", "true")
    monkeypatch.setattr(qwen, "LEDGER", None)
    app = _app()
    assert not app.exception
    assert not any("账本" in item.value for item in [*app.info, *app.warning])


def test_openalex_failure_is_demo_and_has_no_evidence(monkeypatch):
    import research_compass.retrieval as retrieval

    def offline_failure(branches, key, *, intent):
        return SearchOutcome("demo", [Paper("demo-1", "[DEMO]", None, None, None, None, None,
                                             is_demo=True)],
                             [QueryRecord(branches[0].key, branches[0].query, [], "离线故障注入")], "now")

    monkeypatch.setattr(retrieval, "search_papers", offline_failure)
    intent = parse_intent("Gaussian processes for control systems")
    app = _app()
    app.session_state.confirmed_intent = intent
    app.session_state.draft_paths = build_planned_branches(intent)
    app.switch_page("pages/2_Path_Explorer.py").run()
    _button(app, "选择并检索这条路径").click().run()
    assert not app.exception
    assert app.session_state.selected_outcome.mode == "demo"
    assert app.session_state.selected_report is None
    assert any("DEMO 回退" in item.value for item in app.error)


def test_no_eligible_evidence_has_no_claims_or_questions():
    intent = parse_intent("Gaussian processes for control systems")
    branch = build_planned_branches(intent)[0]
    paper = Paper("https://openalex.org/W1", "Unrelated art theory", 2024,
                  "This abstract discusses art theory and visual culture across different regions.",
                  "https://example.org/art", "https://openalex.org/W1", None)
    outcome = SearchOutcome("live", [paper], [QueryRecord(branch.key, branch.query, [paper.id],
        ranked_results=[{"paper_id": paper.id, "raw_rank": 1, "relevant": False,
                         "evidence_eligible": False, "reason": "主题不符"}])], "now")
    report = build_report(outcome, intent, {branch.key: branch.title})
    app = _app()
    app.session_state.confirmed_intent = intent
    app.session_state.draft_paths = [branch]
    app.session_state.selected_path = branch.key
    app.session_state.selected_outcome = outcome
    app.session_state.selected_report = report
    app.switch_page("pages/3_Evidence_Next.py").run()
    assert not app.exception
    assert report.current_work == report.explicit_limitations == report.candidate_questions == []
    assert any("没有足够合格证据" in item.value for item in app.info)
    assert not any("研究方向 ·" in item.value for item in app.markdown)
    assert any("Research Plan Summary" in item.value for item in app.subheader)


def test_saved_live_golden_preserves_direction_with_distinct_queries():
    trace = json.loads((ROOT / "evaluation/cases/badcase_001/original_trace.json").read_text(encoding="utf-8"))
    live = json.loads((ROOT / "evaluation/runs/v3_20261014/golden_qwen_live_20261014.json").read_text(encoding="utf-8"))
    intent, branches = validate_plan(trace["interest"], live["metadata"]["raw_response"])
    assert intent.domain == "Control Theory / Control Systems"
    assert intent.source_method == "Neural Networks"
    assert intent.target_method == "Gaussian Processes"
    assert intent.relationship == "Neural Networks → Gaussian Processes"
    assert intent.explicit_constraints == ()
    assert len(branches) == len({item.query for item in branches}) == 3
    assert all(item.query.isascii() for item in branches)


def test_editing_intent_invalidates_cached_search_and_updates_query():
    app = _app()
    app.text_area[0].set_value("What are reinforcement learning methods in robot control?")
    app.radio[0].set_value("本地规则 V1")
    _button(app, "理解研究意图").click().run()
    previous = app.session_state.draft_paths[0].query
    app.session_state.selected_outcome = object()
    app.session_state.path_outcomes = {"old": object()}
    app.session_state._prototype_snapshot_loaded = True
    app.session_state.golden_v2_mode = True
    next(field for field in app.text_input if field.label == "研究领域").set_value("Medical Imaging")
    _button(app, "保存修改并更新路径").click().run()
    assert not app.exception
    assert app.session_state.get("selected_outcome") is None
    assert app.session_state.get("path_outcomes") is None
    assert not app.session_state.get("_prototype_snapshot_loaded", False)
    assert not app.session_state.get("golden_v2_mode", False)
    assert app.session_state.draft_paths[0].query != previous
    assert "Medical Imaging" in app.session_state.draft_paths[0].query


def test_switching_to_cached_path_does_not_requery(monkeypatch):
    import research_compass.retrieval as retrieval

    calls = []

    def offline_search(branches, key, *, intent):
        calls.append(branches[0].key)
        return SearchOutcome("live", [], [QueryRecord(branches[0].key, branches[0].query, [])], "now")

    monkeypatch.setattr(retrieval, "search_papers", offline_search)
    intent = parse_intent("Compare neural networks and Gaussian processes in control theory")
    app = _app()
    app.session_state.confirmed_intent = intent
    app.session_state.draft_paths = build_planned_branches(intent)[:2]
    app.switch_page("pages/2_Path_Explorer.py").run()
    _button(app, "选择并检索这条路径").click().run()
    _button(app, "选择并检索这条路径").click().run()
    _button(app, "切换到已检索路径").click().run()
    assert not app.exception
    assert len(calls) == 2


def test_next_query_is_carried_back_for_user_confirmed_search(monkeypatch):
    import research_compass.retrieval as retrieval

    seen = []

    def offline_search(branches, key, *, intent):
        seen.append(branches[0].query)
        return SearchOutcome("live", [], [QueryRecord(branches[0].key, branches[0].query, [])], "now")

    monkeypatch.setattr(retrieval, "search_papers", offline_search)
    intent = parse_intent("Gaussian processes for control systems")
    branch = build_planned_branches(intent)[0]
    outcome = SearchOutcome("live", [], [QueryRecord(branch.key, branch.query, [])], "now")
    report = build_report(outcome, intent, {branch.key: branch.title})
    app = _app()
    app.session_state.confirmed_intent = intent
    app.session_state.draft_paths = [branch]
    app.session_state.selected_path = branch.key
    app.session_state.selected_outcome = outcome
    app.session_state.selected_report = report
    app.session_state.path_outcomes = {branch.key: (outcome, report)}
    app.switch_page("pages/3_Evidence_Next.py").run()
    next(field for field in app.text_input if field.label == "下一轮英文检索式").set_value("control systems gaussian process review")
    _button(app, "带着检索式继续探索").click().run()
    assert not app.exception
    assert app.session_state.next_query_draft == "control systems gaussian process review"
    assert any("Research Path Explorer" in item.value for item in app.title)
    app.switch_page("pages/2_Path_Explorer.py").run()
    _button(app, "按此检索式执行 OpenAlex 检索").click().run()
    assert not app.exception
    assert seen == ["control systems gaussian process review"]
    assert app.session_state.selected_outcome.queries[0].query == seen[0]
