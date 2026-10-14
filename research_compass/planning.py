"""Rule-based multilingual intent normalization and query planning.

This module is deliberately deterministic and editable. It does not claim to be
an LLM and records which fields were explicit versus inferred.
"""

from dataclasses import asdict, dataclass, field
import re

from research_compass.exploration import SearchBranch, clean_text


GOALS = {
    "map": "了解研究版图",
    "methods": "比较技术路线",
    "tasks": "寻找具体任务",
    "evaluation": "考察局限与评估",
    "transfer": "从已有方向迁移研究思路",
}

CONCEPTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "Artificial Intelligence": ("artificial intelligence", ("artificial intelligence", "ai", "人工智能")),
    "Neural Networks": ("neural networks", ("neural network", "neural networks", "artificial neural network", "artificial neural networks", "神经网络", "人工神经网络")),
    "Gaussian Processes": ("gaussian processes", ("gaussian process", "gaussian processes", "gaussian process regression", "gaussian process models", "高斯过程", "高斯过程回归")),
    "Reinforcement Learning": ("reinforcement learning", ("reinforcement learning", "deep reinforcement learning", "强化学习")),
    "Model Predictive Control": ("model predictive control", ("model predictive control", "model-predictive control", "mpc", "模型预测控制")),
    "Transformers": ("transformers", ("transformer", "transformers", "transformer-based", "transformer model", "transformer models", "变换器", "Transformer")),
    "Convolutional Neural Networks": ("convolutional neural networks", ("convolutional neural network", "convolutional neural networks", "cnn", "cnns", "卷积神经网络")),
}
DOMAINS: dict[str, tuple[str, ...]] = {
    "Control Theory / Control Systems": (
        "control theory", "control systems", "control system", "control engineering",
        "control method", "intelligent control", "control technology", "robot control",
        "control field", "control law", "control laws", "control performance", "control and robotics", "robotics and control",
        "learning and control", "nonlinear control", "adaptive control",
        "model predictive control", "model-predictive control", "mpc",
        "控制理论", "控制系统", "控制工程", "控制方法", "智能控制", "控制技术", "机器人控制",
    ),
    "Robotics": ("robotics", "robot", "robotic", "机器人", "机器人学"),
    "Medical Imaging": ("medical imaging", "medical image", "医学影像", "医学图像"),
    "Computer Vision": ("computer vision", "image recognition", "计算机视觉", "图像识别"),
    "Materials Science": ("materials science", "material discovery", "材料科学", "材料发现"),
    "Natural Language Processing": ("natural language processing", "language model", "nlp", "自然语言处理", "语言模型"),
}


@dataclass(frozen=True)
class ResearchIntent:
    original_interest: str
    theme: str
    approach: str
    goal: str
    constraints: str = ""
    domain: str = ""
    source_method: str = ""
    target_method: str = ""
    task: str = ""
    relationship: str = ""
    explicit_constraints: tuple[str, ...] = ()
    inferred: tuple[str, ...] = ()
    unconfirmed: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()
    field_provenance: dict[str, str] = field(default_factory=dict)
    parser_version: str = "rules_v2"

    def to_dict(self) -> dict:
        return asdict(self)


def _mentioned(canonical: str, aliases: tuple[str, ...], text: str) -> bool:
    for alias in aliases:
        if re.search(r"[a-zA-Z]", alias):
            if re.search(r"(?<![a-z])" + re.escape(alias.lower()) + r"(?![a-z])", text.lower()):
                return True
        elif alias in text:
            return True
    return False


def normalize_concepts(text: str) -> tuple[str, ...]:
    return tuple(name for name, (_, aliases) in CONCEPTS.items() if _mentioned(name, aliases, text))


def normalize_domain(text: str) -> str:
    for domain, aliases in DOMAINS.items():
        if _mentioned(domain, aliases, text):
            return domain
    return ""


def suggest_components(interest: str) -> tuple[str, str]:
    """Compatibility helper retained for the existing UI/tests."""
    intent = parse_intent(interest)
    theme = intent.domain or intent.target_method or intent.theme
    approach = intent.source_method or intent.target_method or intent.approach
    return clean_text(theme), clean_text(approach)


def _explicit_constraints(text: str) -> tuple[str, ...]:
    # Extract only after explicit constraint cues, never from example placeholders.
    patterns = (
        r"(?:限制|约束|条件|要求|constrained by|with the constraint(?:s)? of)\s*[:：]?\s*([^。.!?，,;；]+)",
    )
    found: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            value = clean_text(match.group(1))
            if value and value.lower() not in {"none", "无", "没有"}:
                found.append(value)
    return tuple(found)


def _query_terms(*values: str) -> str:
    """Return compact, case-insensitively unique search terms."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for term in clean_text(value).split():
            if term.casefold() not in seen:
                result.append(term)
                seen.add(term.casefold())
    return " ".join(result)


def parse_intent(interest: str, *, goal: str | None = None, clarified_constraints: str = "") -> ResearchIntent:
    """Parse general Chinese/English research interests into editable slots."""
    text = clean_text(interest)
    if not text:
        raise ValueError("研究兴趣不能为空")
    concepts = normalize_concepts(text)
    domain = normalize_domain(text)
    comparison = bool(re.search(r"\b(compare|comparison|versus|vs\.?|difference|differentiate)\b|比较|对比|区别", text, re.I))
    transfer = bool(re.search(r"\b(inspire|transfer|adapt|guide|informed by|build on|from .+ to)\b|迁移|借鉴|启发|指导|转化", text, re.I))
    source = concepts[0] if transfer and concepts else ""
    target = concepts[-1] if transfer and len(concepts) > 1 else ""
    if not transfer and comparison and len(concepts) > 1:
        source, target = concepts[0], concepts[-1]
    relation = "" if not (comparison or transfer) else ("comparison+transfer" if comparison and transfer else "transfer" if transfer else "comparison")
    inferred: list[str] = []
    if domain:
        inferred.append(f"研究领域识别：{domain}（根据术语匹配，需用户确认）")
    if concepts:
        inferred.append("方法概念由中英文术语词表规范化，需用户确认角色")
    explicit_constraints = _explicit_constraints(text)
    if clarified_constraints.strip():
        explicit_constraints += (clean_text(clarified_constraints),)
    found_goal = goal or ("transfer" if transfer else "methods" if comparison else "map")
    if domain and concepts and relation:
        theme = f"{domain}: {', '.join(concepts)}"
        task = "方法比较与研究思路迁移" if comparison and transfer else "方法比较" if comparison else "研究思路迁移" if transfer else "探索研究版图"
    else:
        theme = clean_text(" ".join(filter(None, (domain, *concepts)))) or text
        task = "方法比较" if comparison else "探索研究版图"
    unconfirmed = ("具体应用任务或控制对象",) if domain and "Control" in domain else ("具体应用任务",)
    return ResearchIntent(
        original_interest=text,
        theme=theme,
        approach=", ".join(concepts),
        goal=found_goal,
        constraints="; ".join(explicit_constraints),
        domain=domain,
        source_method=source,
        target_method=target,
        task=task,
        relationship=(f"{source} → {target}" if transfer and source and target else f"{source} → {domain}" if transfer and source and domain else "迁移方向未确认" if transfer else "对比" if comparison else ""),
        explicit_constraints=explicit_constraints,
        inferred=tuple(inferred),
        unconfirmed=unconfirmed,
        concepts=concepts,
        field_provenance={
            "domain": "explicit term; canonical label normalized" if domain else "unconfirmed",
            "concepts": "explicit bilingual terms; canonical labels normalized" if concepts else "unconfirmed",
            "source_method_role": "inferred from mention order and transfer cue" if source else "unconfirmed",
            "target_method_role": "inferred from mention order and target cue" if target else "unconfirmed",
            "task": "inferred from comparison and transfer language" if relation else "unconfirmed",
            "relationship_direction": "inferred from concept order and transfer wording" if transfer else "explicit comparison cue" if comparison else "unconfirmed",
            "constraints": "explicitly stated by user" if explicit_constraints else "none stated",
            "goal": "user selected during clarification" if goal else "inferred from wording",
        },
    )


def build_planned_branches(intent: ResearchIntent) -> list[SearchBranch]:
    """Generate distinct branches from parsed objects and requested relation."""
    domain = intent.domain or intent.theme
    if not domain:
        raise ValueError("研究主题不能为空")
    branches: list[SearchBranch] = []
    aliases = {name: pair[1] for name, pair in CONCEPTS.items()}
    canonical = {name: pair[0] for name, pair in CONCEPTS.items()}
    domain_terms = "Control Theory Control Systems" if domain == "Control Theory / Control Systems" else domain.replace(" / ", " ")
    source = intent.source_method or (intent.concepts[0] if intent.concepts else "")
    target = intent.target_method or (intent.concepts[-1] if intent.concepts else "")
    if source:
        branches.append(SearchBranch("source_method", f"{source} 文献", f"从来源方法研究中提取可迁移思路：{source}", _query_terms(domain_terms, canonical.get(source, source)), focus_method=source, required_methods=(source,), query_aliases=aliases.get(source, ())))
    if target:
        branches.append(SearchBranch("target_method", f"{target} 文献", f"检索目标方法在该领域的已有工作：{target}", _query_terms(domain_terms, canonical.get(target, target)), focus_method=target, required_methods=(target,), query_aliases=aliases.get(target, ())))
    if source and target and intent.relationship:
        has_transfer = "→" in intent.relationship
        comparison_key = "comparison_transfer" if has_transfer else "method_comparison"
        comparison_title = "方法比较与思路迁移" if has_transfer else "方法比较"
        comparison_purpose = f"比较 {source} 与 {target}" + (" 并追踪思路迁移" if has_transfer else "")
        branches.append(SearchBranch(
            comparison_key, comparison_title,
            comparison_purpose,
            _query_terms(domain_terms, canonical.get(source, source), canonical.get(target, target), "comparison"),
            required_methods=tuple(filter(None, (source, target))),
            query_aliases=tuple(dict.fromkeys((*aliases.get(source, ()), *aliases.get(target, ())))),
        ))
    if not branches:
        tokens = intent.concepts or normalize_concepts(intent.original_interest)
        normalized = [canonical[name] for name in tokens]
        terms = clean_text(" ".join([domain_terms, *normalized]))
        branches.append(SearchBranch("topic_map", "主题版图", "检索已识别研究主题的代表性工作", terms))
    return branches


def default_planned_keys(goal: str) -> list[str]:
    return ["source_method", "target_method", "comparison_transfer", "method_comparison", "topic_map"]
