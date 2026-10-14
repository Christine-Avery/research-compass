from research_compass.evidence import build_report, landscape_representatives
from research_compass.exploration import build_branches
from research_compass.planning import ResearchIntent, build_planned_branches, parse_intent, suggest_components
from research_compass.retrieval import Paper, QueryRecord, SearchOutcome, assess_relevance
from types import SimpleNamespace


def test_chinese_transfer_intent_and_distinct_branches():
    text = "神经网络和高斯过程在控制理论学术上的区别，我希望能从已经很多的神经网络文章中找到一些灵感，指导我做高斯过程相关的研究。"
    intent = parse_intent(text)
    assert intent.domain == "Control Theory / Control Systems"
    assert intent.source_method == "Neural Networks"
    assert intent.target_method == "Gaussian Processes"
    assert intent.task == "方法比较与研究思路迁移"
    assert intent.relationship == "Neural Networks → Gaussian Processes"
    assert intent.explicit_constraints == ()
    assert not any(word in intent.constraints for word in ("低数据量", "安全性"))
    branches = build_planned_branches(intent)
    assert [branch.key for branch in branches] == ["source_method", "target_method", "comparison_transfer"]
    assert len({branch.query for branch in branches}) == 3
    assert "Control Theory" in branches[0].query
    assert "neural networks" in branches[0].query
    assert "gaussian processes" in branches[1].query
    assert build_branches(text)[0].query == text


def test_multilingual_parser_generalizes_to_other_topics():
    en = parse_intent("Can ideas from transformer models inspire computer vision research?")
    zh = parse_intent("我想比较强化学习和模型预测控制在机器人路径规划中的应用。")
    assert en.source_method == "Transformers"
    assert en.target_method == ""
    assert en.relationship == "Transformers → Computer Vision"
    assert en.domain == "Computer Vision"
    assert zh.concepts == ("Reinforcement Learning", "Model Predictive Control")
    assert zh.relationship == "对比"
    assert zh.explicit_constraints == ()
    assert build_planned_branches(zh)[-1].key == "method_comparison"
    robotics = parse_intent("AI for robot control")
    assert robotics.domain == "Control Theory / Control Systems"
    assert robotics.concepts == ("Artificial Intelligence",)
    assert "artificial intelligence" in build_planned_branches(robotics)[0].query


def test_evidence_gate_rejects_irrelevant_paper_and_keeps_raw_rank():
    intent = parse_intent("Neural networks and Gaussian processes in control theory: compare and transfer ideas")
    branch = build_planned_branches(intent)[0]
    irrelevant = Paper("W0", "AI ethics and solar storms", 2024, "This paper discusses art theory and solar storm effects on society at large.", "https://example.org", "https://openalex.org/W0", None)
    assessment = assess_relevance(irrelevant, branch, intent)
    assert assessment["status"] == "Retrieved"
    assert not assessment["relevant"]
    assert not assessment["evidence_eligible"]


def test_control_field_synonym_recovers_relevant_control_abstract():
    intent = parse_intent("Neural networks and Gaussian processes in control theory")
    branch = build_planned_branches(intent)[0]
    paper = Paper(
        "W-control", "Theory and applications of neural networks for industrial control systems", 1992,
        "The theory and the applications of artificial neural networks, especially in a control field, are described. "
        "Recurrent networks and feedforward networks are discussed. Applications to planning, diagnosis, and control are examined.",
        "https://doi.org/10.1109/41.170966", "https://openalex.org/W-control", "https://doi.org/10.1109/41.170966",
    )
    assessment = assess_relevance(paper, branch, intent)
    assert assessment["relevant"]
    assert assessment["evidence_eligible"]


def test_mpc_abstract_is_control_relevant_without_title_shortcut():
    intent = parse_intent("Compare neural networks and Gaussian processes in control theory")
    branch = build_planned_branches(intent)[-1]
    abstract = (
        "This study presents model predictive control for uncertain dynamical systems. "
        "Bayesian neural networks estimate model uncertainty and Gaussian processes provide "
        "a comparison in the same control task. Both methods are evaluated with simulation "
        "results and the limitations of the comparison are discussed in the paper."
    )
    paper = Paper("W-mpc", "A generic title", 2024, abstract,
                  "https://example.org/paper", "https://openalex.org/W-mpc", None)
    assessment = assess_relevance(paper, branch, intent)
    assert assessment["status"] == "Evidence Eligible"


def test_report_uses_only_evidence_eligible_papers_and_exact_supported_sentences():
    intent = parse_intent("Neural networks and Gaussian processes in control theory: compare and transfer ideas")
    abstract = (
        "This study presents Gaussian process models for control systems in uncertain settings. "
        "Gaussian process control systems remain a limiting factor when physical control is performed remotely."
    )
    paper = Paper("W1", "Gaussian process control", 2024, abstract, "https://doi.org/10.1234/test", "https://openalex.org/W1", "https://doi.org/10.1234/test", ["target_method"])
    eligible = {"rank": 1, "paper_id": paper.id, "status": "Evidence Eligible", "relevant": True, "evidence_eligible": True}
    outcome = SearchOutcome("live", [paper], [QueryRecord("target_method", "control gaussian process", [paper.id], ranked_results=[eligible])], "now")
    report = build_report(outcome, intent, {"target_method": "Gaussian Processes"})
    assert report is not None
    assert report.landscape[0].paper_ids == [paper.id]
    assert report.current_work[0].quote in abstract
    assert report.explicit_limitations[0].quote in abstract
    assert report.candidate_questions[0].status == "inferred_unverified"
    assert "不证明研究空白" in report.candidate_questions[0].rationale
    legacy_row = SimpleNamespace(paper_ids=[paper.id])
    assert landscape_representatives(legacy_row, outcome) == [paper.title]


def test_claim_uses_exact_adjacent_abstract_sentences_when_topic_is_split():
    intent = parse_intent("Gaussian processes in control theory")
    abstract = (
        "However, decentralized learning is limited by poor control laws when models are local. "
        "We propose distributed aggregation of Gaussian process models and evaluate it on a common task. "
        "The paper discusses unrelated implementation details in a separate section."
    )
    paper = Paper("W-adjacent", "GP control", 2024, abstract,
                  "https://example.org/gp", "https://openalex.org/W-adjacent", None, ["target_method"])
    hit = {"paper_id": paper.id, "relevant": True, "evidence_eligible": True}
    outcome = SearchOutcome("live", [paper], [QueryRecord("target_method", "control gaussian process",
        [paper.id], ranked_results=[hit])], "now")
    report = build_report(outcome, intent, {"target_method": "GP control"})
    assert report.current_work and report.explicit_limitations
    assert all(item.quote in abstract for item in [*report.current_work, *report.explicit_limitations])
    assert all(item.paper_id == paper.id for item in [*report.current_work, *report.explicit_limitations])


def test_report_excludes_retrieved_but_irrelevant_and_does_not_fill():
    intent = parse_intent("Neural networks and Gaussian processes in control theory")
    irrelevant = Paper("W2", "AI ethics", 2024, "AI ethics remains a difficult challenge for modern societies in many contexts.", "https://example.org", "https://openalex.org/W2", None)
    hit = {"rank": 1, "paper_id": irrelevant.id, "status": "Retrieved", "relevant": False, "evidence_eligible": False}
    report = build_report(SearchOutcome("live", [irrelevant], [QueryRecord("target_method", "q", [irrelevant.id], ranked_results=[hit])], "now"), intent, {})
    assert report.landscape[0].paper_ids == []
    assert report.current_work == []
    assert report.explicit_limitations == []
    assert report.candidate_questions == []
    assert report.insufficiency_reasons
