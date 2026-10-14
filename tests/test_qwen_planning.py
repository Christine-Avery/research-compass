from research_compass.qwen_planning import validate_plan
from evaluation.run_v3_intent_comparison import is_complex_interest


def test_qwen_output_is_validated_and_constraints_must_be_explicit():
    interest = "神经网络和高斯过程在控制理论学术上的区别，希望从神经网络文章获得灵感，指导高斯过程研究。"
    data = {
        "intent": {
            "domain": "Control Theory / Control Systems",
            "concepts": ["Neural Networks", "Gaussian Processes"],
            "source_method": "Neural Networks",
            "target_method": "Gaussian Processes",
            "task": "方法比较与研究思路迁移",
            "relationship_type": "comparison_transfer",
            "explicit_constraints": ["低数据量", "安全性"],
            "inferred": ["用户希望迁移研究思路"],
            "unconfirmed": ["具体控制任务"],
        },
        "branches": [
            {"key": "nn_source", "title": "神经网络来源研究", "purpose": "了解来源方法", "query": "control theory neural networks", "focus_method": "Neural Networks", "required_methods": ["Neural Networks"]},
            {"key": "gp_target", "title": "高斯过程目标研究", "purpose": "了解目标方法", "query": "control theory gaussian processes", "focus_method": "Gaussian Processes", "required_methods": ["Gaussian Processes"]},
        ],
    }
    intent, branches = validate_plan(interest, data)
    assert intent.domain == "Control Theory / Control Systems"
    assert intent.source_method == "Neural Networks"
    assert intent.target_method == "Gaussian Processes"
    assert intent.relationship == "Neural Networks → Gaussian Processes"
    assert intent.explicit_constraints == ()
    assert intent.field_provenance["constraints"] == "未明确提出"
    assert [branch.query for branch in branches] == ["control theory neural networks", "control theory gaussian processes"]


def test_qwen_plan_accepts_english_transformer_transfer_without_golden_case_logic():
    interest = "Can neural network ideas inspire Gaussian process methods for control systems?"
    data = {
        "intent": {
            "domain": "Control Theory / Control Systems", "concepts": ["Neural Networks", "Gaussian Processes"],
            "source_method": "Neural Networks", "target_method": "Gaussian Processes",
            "task": "method transfer", "relationship_type": "transfer", "explicit_constraints": [],
            "inferred": [], "unconfirmed": [],
        },
        "branches": [{"key": "target", "title": "Target", "purpose": "Target methods", "query": "Gaussian process control systems", "focus_method": "Gaussian Processes", "required_methods": ["Gaussian Processes"]}],
    }
    intent, branches = validate_plan(interest, data)
    assert intent.relationship == "Neural Networks → Gaussian Processes"
    assert branches[0].required_methods == ("Gaussian Processes",)


def test_v3_offline_router_uses_only_query_wording():
    assert is_complex_interest("Compare neural networks and Gaussian processes for control.")
    assert is_complex_interest("我想从神经网络获得灵感，指导高斯过程研究。")
    assert not is_complex_interest("What are common neural network methods in robot control?")
