import csv
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_evaluation_page_saves_all_source_rows_to_separate_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "false")
    root = Path(__file__).parents[1]
    output = tmp_path / "human_labels.csv"
    monkeypatch.setenv("RESEARCH_COMPASS_HUMAN_LABELS_PATH", str(output))
    test = AppTest.from_file(str(root / "app.py"), default_timeout=15).run()
    test.switch_page("pages/2_Evaluation.py").run()
    assert not test.exception
    assert any("Human Evaluation" in element.value for element in test.title)
    assert len(test.radio) == 2
    button_labels = {element.label for element in test.button}
    assert {"保存进度", "保存并上一条", "保存并下一条", "跳过（不保存本条）"}.issubset(button_labels)
    test.radio[0].set_value("0 — 不相关")
    test.radio[1].set_value("否 — 不适合进入 Evidence Generation")
    test.button[0].click().run()
    assert not test.exception
    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        saved = list(csv.DictReader(handle))
    assert len(saved) == 35
    assert saved[0]["human_relevance_label"] == "0"
    assert saved[0]["human_evidence_eligible_label"] == "no"
    assert saved[0]["review_status"] == "complete"


def test_public_evaluation_route_runs_read_only(tmp_path, monkeypatch):
    root = Path(__file__).parents[1]
    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "true")
    monkeypatch.setenv("RESEARCH_COMPASS_HUMAN_LABELS_PATH", str(tmp_path / "public_labels.csv"))
    test = AppTest.from_file(str(root / "app.py"), default_timeout=15).run()
    test.switch_page("pages/2_Evaluation.py").run()
    assert not test.exception
    assert not test.selectbox
    assert any("公网评测仅展示" in element.value for element in test.info)
    assert all(button.disabled for button in test.button if button.label.startswith(("保存", "跳过")))
    assert all(radio.disabled for radio in test.radio)
    assert not (tmp_path / "public_labels.csv").exists()
