"""Abstract-only evidence assembly with independent relevance/support gates."""

from dataclasses import asdict, dataclass, field
import re

from research_compass.planning import CONCEPTS, DOMAINS, ResearchIntent
from research_compass.retrieval import Paper, SearchOutcome


LIMITATION_CUE = re.compile(
    r"\b(remains? (?:a |an )?(?:limiting|challenge|difficult)|limiting factor|limited by|"
    r"limitations? (?:such as|include|is|are)|fragilit\w*|instruction-following errors?|"
    r"high sensitivity|high computational demands?|poor control performance|lack of|suffers? from|fails? to|shortcoming)\b|"
    r"局限|限制|仍然是.{0,8}(?:挑战|困难)|缺乏|无法(?:实现|处理|解决)", re.I,
)
STATUS_CUE = re.compile(r"\b(this (?:paper|study|work)|we (?:propose|present|develop|investigate)|review|survey)\b|本文|本研究|我们(?:提出|展示|开发|研究)", re.I)


@dataclass(frozen=True)
class EvidenceQuote:
    kind: str
    quote: str
    paper_id: str
    paper_title: str
    source_url: str | None
    openalex_url: str | None
    branch_keys: list[str]
    relevance_status: str = "Evidence Eligible"
    support_status: str = "Exact abstract sentence"
    claim_scope: str = "This abstract only; full text not verified"


@dataclass(frozen=True)
class LandscapeRow:
    branch_key: str
    branch_title: str
    paper_ids: list[str]
    representative_titles: list[str]
    retrieved_count: int = 0
    relevant_count: int = 0
    evidence_eligible_count: int = 0
    exclusions: list[str] | None = None


@dataclass(frozen=True)
class CandidateQuestion:
    text: str
    status: str
    opportunity: str
    rationale: str
    evidence_paper_ids: list[str]
    verification_step: str


@dataclass(frozen=True)
class ExplorationReport:
    method: str
    scope: str
    landscape: list[LandscapeRow]
    current_work: list[EvidenceQuote]
    explicit_limitations: list[EvidenceQuote]
    candidate_questions: list[CandidateQuestion]
    insufficiency_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def landscape_representatives(row: LandscapeRow, outcome: SearchOutcome) -> list[str]:
    titles = getattr(row, "representative_titles", None)
    if titles is not None:
        return titles
    by_id = {paper.id: paper.title for paper in outcome.papers if not paper.is_demo}
    return [by_id[paper_id] for paper_id in row.paper_ids[:2] if paper_id in by_id]


def _sentences(abstract: str) -> list[str]:
    """Split Chinese/English mixed abstracts while retaining original substrings."""
    return [part.strip() for part in re.split(r"(?<=[.!?。！？])(?:\s+|(?=[\u3400-\u9fff]))", abstract) if part.strip()]


def _abstract_sufficient(abstract: str) -> bool:
    # Count Latin words and CJK characters separately so Chinese abstracts do not
    # fail the English whitespace-token length heuristic.
    latin_words = len(re.findall(r"[A-Za-z0-9]+", abstract))
    cjk_chars = len(re.findall(r"[\u3400-\u9fff]", abstract))
    return latin_words >= 20 or cjk_chars >= 50 or (latin_words >= 8 and cjk_chars >= 20)


def _topic_aliases(intent: ResearchIntent) -> tuple[str, ...]:
    aliases: list[str] = []
    if intent.domain:
        for name, values in DOMAINS.items():
            if name == intent.domain:
                aliases.extend(values)
    for concept in (tuple(filter(None, (intent.source_method, intent.target_method))) or intent.concepts):
        if concept in CONCEPTS:
            aliases.extend(CONCEPTS[concept][1])
    return tuple(dict.fromkeys(aliases))


def _topic_supported(sentence: str, intent: ResearchIntent) -> bool:
    def has_one(aliases: tuple[str, ...]) -> bool:
        return any(
            alias in sentence if not re.search(r"[a-z]", alias, re.I)
            else bool(re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", sentence, re.I))
            for alias in aliases
        )
    domain_aliases: tuple[str, ...] = ()
    for domain, aliases in DOMAINS.items():
        if domain == intent.domain:
            domain_aliases = aliases
            break
    methods = tuple(filter(None, (intent.source_method, intent.target_method))) or intent.concepts
    method_aliases = tuple(alias for method in methods for alias in CONCEPTS.get(method, ("", ()))[1])
    return bool(domain_aliases and method_aliases and has_one(domain_aliases) and has_one(method_aliases))


def _quote(paper: Paper, kind: str, cue: re.Pattern[str], intent: ResearchIntent) -> EvidenceQuote | None:
    abstract = paper.abstract or ""
    if not _abstract_sufficient(abstract):
        return None
    sentences = _sentences(abstract)
    spans: list[tuple[int, int]] = []
    cursor = 0
    for sentence in sentences:
        start = abstract.find(sentence, cursor)
        if start < 0:
            continue
        end = start + len(sentence)
        spans.append((start, end))
        cursor = end
    for index, (start, end) in enumerate(spans):
        sentence = abstract[start:end]
        if len(sentence) < 25 or not cue.search(sentence):
            continue
        windows = [(start, end)]
        if index:
            windows.append((spans[index - 1][0], end))
        if index + 1 < len(spans):
            windows.append((start, spans[index + 1][1]))
        for left, right in windows:
            exact_quote = abstract[left:right]
            if _topic_supported(exact_quote, intent):
                return EvidenceQuote(kind, exact_quote, paper.id, paper.title, paper.source_url, paper.openalex_url, list(paper.found_by))
    return None


def _evidence_eligible_ids(outcome: SearchOutcome) -> set[str]:
    eligible = set()
    for record in outcome.queries:
        eligible.update(
            hit.get("paper_id") for hit in record.ranked_results
            if hit.get("evidence_eligible") and hit.get("paper_id")
        )
    return eligible


def build_report(outcome: SearchOutcome, intent: ResearchIntent, branch_titles: dict[str, str]) -> ExplorationReport | None:
    if outcome.mode == "demo":
        return None
    eligible_ids = _evidence_eligible_ids(outcome)
    papers_by_id = {paper.id: paper for paper in outcome.papers if not paper.is_demo}
    eligible_papers = [papers_by_id[paper_id] for paper_id in eligible_ids if paper_id in papers_by_id]
    landscape: list[LandscapeRow] = []
    insufficient: list[str] = []
    for record in outcome.queries:
        record_hits = record.ranked_results
        ids = list(dict.fromkeys(hit.get("paper_id") for hit in record_hits if hit.get("paper_id")))
        rel_ids = [hit.get("paper_id") for hit in record_hits if hit.get("relevant")]
        ok_ids = [hit.get("paper_id") for hit in record_hits if hit.get("evidence_eligible")]
        titles = [papers_by_id[paper_id].title for paper_id in ok_ids[:2] if paper_id in papers_by_id]
        excluded = [hit.get("reason", "未准入") for hit in record_hits if not hit.get("evidence_eligible")]
        landscape.append(LandscapeRow(record.branch_key, branch_titles.get(record.branch_key, record.branch_key), ok_ids, titles, len(ids), len(set(rel_ids)), len(set(ok_ids)), excluded[:5]))
        if not ok_ids:
            insufficient.append(f"{branch_titles.get(record.branch_key, record.branch_key)}：{len(ids)} 篇检索命中中没有满足主题与摘要准入条件的论文。")
    current_work = [quote for paper in eligible_papers if (quote := _quote(paper, "current_work", STATUS_CUE, intent))][:4]
    limitations = [quote for paper in eligible_papers if (quote := _quote(paper, "explicit_limitation", LIMITATION_CUE, intent))][:4]
    questions: list[CandidateQuestion] = []
    # Research questions need direct relevant evidence; a search result count or
    # inferred absence never suffices. No candidate is fabricated on empty evidence.
    anchors = limitations or current_work
    for anchor in anchors[:2]:
        transfer = bool(intent.relationship and intent.source_method and intent.target_method)
        question = (
            f"在{intent.domain or intent.theme}的相同任务中，{intent.source_method} 文献的哪些建模思路"
            f"值得与 {intent.target_method} 方法比较，并能否产生可验证的改进？"
            if transfer else
            f"在{intent.domain or intent.theme}中，摘要所述的研究问题能否通过 {intent.target_method or '目标方法'} 方法处理，并在何种任务下得到验证？"
        )
        questions.append(CandidateQuestion(
            question, "inferred_unverified",
            "由相关论文摘要启发的潜在研究机会；尚未确认其新颖性或研究覆盖情况。",
            "该摘要只支持所引句子的内容，不证明研究空白或方法迁移有效；来源方法文献仍需检索。" if transfer else
            "该摘要只支持所引句子的内容，不证明研究空白或方法迁移有效。",
            [anchor.paper_id], "检索来源方法文献并核查全文，在相同任务下制定可证伪的比较实验。" if transfer else
            "扩展检索、检查全文和相关工作，再制定可证伪的比较实验。",
        ))
    if not eligible_papers:
        insufficient.append("没有论文通过 Evidence Eligible；研究版图、事实性结论和候选问题均不生成。")
    elif not current_work and not limitations:
        insufficient.append("有主题相关且摘要充分的论文，但未找到包含研究主题术语的现状陈述或明确局限；因此不生成候选问题。")
    return ExplorationReport(
        "abstract_rules_v2_relevance_gated",
        "仅覆盖本轮 OpenAlex 摘要；未核验全文，也不代表系统性综述或研究领域完整覆盖。",
        landscape, current_work, limitations, questions, list(dict.fromkeys(insufficient)),
    )
