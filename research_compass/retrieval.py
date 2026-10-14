"""OpenAlex retrieval with preserved API order, relevance, and evidence gates."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from pyalex import Works, config

from research_compass.exploration import SearchBranch
from research_compass.planning import CONCEPTS, ResearchIntent, _mentioned


@dataclass
class Paper:
    id: str
    title: str
    year: int | None
    abstract: str | None
    source_url: str | None
    openalex_url: str | None
    doi: str | None
    found_by: list[str] = field(default_factory=list)
    is_demo: bool = False


@dataclass
class QueryRecord:
    branch_key: str
    query: str
    returned_ids: list[str]
    error: str | None = None
    ranked_results: list[dict[str, Any]] = field(default_factory=list)
    raw_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SearchOutcome:
    mode: str
    papers: list[Paper]
    queries: list[QueryRecord]
    retrieved_at: str
    notice: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def paper_from_work(work: dict[str, Any], branch_key: str) -> Paper:
    location = work.get("primary_location") or {}
    oa_location = work.get("best_oa_location") or {}
    url = location.get("landing_page_url") or work.get("doi") or oa_location.get("landing_page_url")
    abstract = work.get("abstract")
    if not isinstance(abstract, str) and work.get("abstract_inverted_index"):
        try:
            abstract = work["abstract"]
        except KeyError:
            abstract = None
    return Paper(
        id=str(work.get("id") or ""), title=str(work.get("title") or work.get("display_name") or "Untitled work"),
        year=work.get("publication_year"), abstract=abstract if isinstance(abstract, str) else None,
        source_url=url, openalex_url=work.get("id"), doi=work.get("doi"), found_by=[branch_key],
    )


_DOMAIN_TERMS = {
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


def assess_relevance(paper: Paper, branch: SearchBranch, intent: ResearchIntent | None) -> dict[str, Any]:
    """Retrieved != Relevant != Evidence Eligible; require domain and method in abstract."""
    if intent is None:
        return {"retrieved": True, "status": "Retrieved", "relevant": None, "evidence_eligible": False, "relevance_score": None, "reason": "缺少结构化意图，尚未评估"}
    abstract = paper.abstract or ""
    aliases = _DOMAIN_TERMS.get(intent.domain, (intent.domain,) if intent.domain else ())
    has_domain = bool(abstract and aliases and _mentioned(intent.domain, aliases, abstract))
    methods = branch.required_methods or tuple(filter(None, (branch.focus_method or intent.target_method or intent.source_method,)))
    if not methods:
        methods = intent.concepts
    mention = {method: bool(abstract and _mentioned(method, CONCEPTS.get(method, (method.lower(), (method,)))[1], abstract)) for method in methods}
    has_methods = bool(mention) and all(mention.values())
    relevant = bool(has_domain and has_methods)
    has_url = bool(paper.source_url or paper.openalex_url)
    eligible = relevant and abstract_sufficient(abstract) and has_url and not paper.is_demo
    reasons = ["摘要包含领域术语" if has_domain else "摘要未确认领域术语"]
    reasons.extend(f"摘要{'包含' if present else '未包含'}方法：{method}" for method, present in mention.items())
    if not abstract:
        reasons.append("无摘要")
    if relevant and not eligible:
        reasons.append("摘要长度不足或来源链接缺失，未准入证据")
    title = paper.title or ""
    title_only = not relevant and any(_mentioned(intent.domain, aliases, title) for _ in [0]) if aliases else False
    return {
        "retrieved": True,
        "status": "Evidence Eligible" if eligible else "Relevant" if relevant else "Retrieved",
        "relevant": relevant,
        "evidence_eligible": eligible,
        "relevance_score": round((0.5 if has_domain else 0) + (0.5 if has_methods else 0), 2),
        "method_mentions": mention,
        "title_support_only": title_only,
        "reason": "；".join(reasons),
    }


def _raw_mapping(work: Any) -> dict[str, Any]:
    try:
        return dict(work)
    except Exception:
        return {"serialization_error": "raw OpenAlex record could not be converted"}


def abstract_sufficient(abstract: str | None) -> bool:
    if not abstract:
        return False
    words = len(abstract.split())
    cjk = sum("\u3400" <= char <= "\u9fff" for char in abstract)
    return words >= 20 or cjk >= 50 or (words >= 8 and cjk >= 20)


def _error_label(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status == 429:
        return "OpenAlex 额度或请求频率已达到限制（HTTP 429）"
    if status:
        return f"OpenAlex 返回 HTTP {status}"
    return "OpenAlex 网络请求失败或超时"


def _demo_papers() -> list[Paper]:
    return [
        Paper("demo-1", "[DEMO 示例] 论文结果卡片 A", None, "这是用于演示页面布局的模拟数据，不代表真实论文、摘要或研究证据。", None, None, None, is_demo=True),
        Paper("demo-2", "[DEMO 示例] 论文结果卡片 B", None, "配置免费 OpenAlex API key 后，可在相同页面查看实时检索结果。", None, None, None, is_demo=True),
    ]


def search_papers(
    branches: list[SearchBranch], api_key: str | None = None, *, per_branch: int = 5,
    search_factory: Callable[[], Any] = Works, intent: ResearchIntent | None = None,
) -> SearchOutcome:
    """Run branches; raw rank is immutable while assessment is added alongside."""
    config.api_key = api_key or None
    unique: list[Paper] = []
    by_id: dict[str, Paper] = {}
    by_doi: dict[str, Paper] = {}
    records: list[QueryRecord] = []
    errors: list[str] = []
    for branch in branches:
        try:
            works = search_factory().search(branch.query).filter(has_abstract=True).get(per_page=per_branch)
            ids: list[str] = []
            ranked: list[dict[str, Any]] = []
            raw: list[dict[str, Any]] = []
            for rank, work in enumerate(works, start=1):
                paper = paper_from_work(work, branch.key)
                if not paper.id:
                    continue
                ids.append(paper.id)
                raw.append(_raw_mapping(work))
                id_key = paper.id.lower().rstrip("/")
                doi_key = (paper.doi or "").lower().rstrip("/")
                decision = assess_relevance(paper, branch, intent)
                existing_by_id = by_id.get(id_key)
                existing_by_doi = by_doi.get(doi_key) if doi_key else None
                existing = existing_by_id or existing_by_doi
                if existing_by_id and existing_by_doi and existing_by_id is not existing_by_doi:
                    absorbed = existing_by_doi
                    for found_branch in absorbed.found_by:
                        if found_branch not in existing_by_id.found_by:
                            existing_by_id.found_by.append(found_branch)
                    unique[:] = [known for known in unique if known is not absorbed]
                    by_id = {key: existing_by_id if value is absorbed else value for key, value in by_id.items()}
                    by_doi = {key: existing_by_id if value is absorbed else value for key, value in by_doi.items()}
                    existing = existing_by_id
                if existing:
                    if branch.key not in existing.found_by:
                        existing.found_by.append(branch.key)
                    by_id[id_key] = existing
                    if doi_key:
                        by_doi[doi_key] = existing
                    decision["duplicate_of"] = existing.id
                else:
                    unique.append(paper)
                    by_id[id_key] = paper
                    if doi_key:
                        by_doi[doi_key] = paper
                ranked.append({"rank": rank, "raw_rank": rank, "paper_id": paper.id, **decision})
            relevance_order = sorted(
                ranked,
                key=lambda hit: (
                    bool(hit.get("evidence_eligible")), bool(hit.get("relevant")),
                    hit.get("relevance_score") if hit.get("relevance_score") is not None else -1,
                    -int(hit.get("raw_rank") or 0),
                ), reverse=True,
            )
            for relevance_rank, hit in enumerate(relevance_order, start=1):
                hit["relevance_rank"] = relevance_rank
            records.append(QueryRecord(branch.key, branch.query, ids, ranked_results=ranked, raw_results=raw))
        except Exception as exc:
            label = _error_label(exc)
            errors.append(label)
            records.append(QueryRecord(branch.key, branch.query, [], label))
            if "429" in label:
                break
    retrieved_at = datetime.now(timezone.utc).isoformat()
    if unique:
        return SearchOutcome("partial" if errors else "live", unique, records, retrieved_at, "；".join(dict.fromkeys(errors)) if errors else None)
    if errors:
        return SearchOutcome("demo", _demo_papers(), records, retrieved_at, "实时检索失败：" + "；".join(dict.fromkeys(errors)))
    return SearchOutcome("live", [], records, retrieved_at, "没有找到匹配的论文，可修改检索式后重试。")
