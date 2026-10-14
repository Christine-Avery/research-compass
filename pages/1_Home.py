"""Research Compass: paired exploratory search and abstract-grounded exploration."""

from dataclasses import replace
import json
import os

from dotenv import load_dotenv
import streamlit as st

from research_compass.evidence import ExplorationReport, build_report, landscape_representatives
from research_compass.exploration import SearchBranch, build_branches
from research_compass.planning import GOALS, ResearchIntent, build_planned_branches, default_planned_keys, parse_intent
from research_compass.qwen_planning import QwenPlanningError, plan_with_qwen
from research_compass.retrieval import SearchOutcome, abstract_sufficient, search_papers
from research_compass.trace import build_paired_trace


load_dotenv()


def api_key() -> str | None:
    value = os.getenv("OPENALEX_API_KEY")
    if value:
        return value.strip()
    try:
        value = st.secrets.get("OPENALEX_API_KEY")
    except (FileNotFoundError, KeyError):
        return None
    return str(value).strip() if value else None


def show_papers(outcome: SearchOutcome, *, title: str) -> None:
    st.subheader(title)
    if outcome.mode == "demo":
        st.error("DEMO 模式：以下卡片是模拟数据，不是真实论文或研究证据。")
    elif outcome.mode == "partial":
        st.warning("部分实时结果：部分查询失败；显示的论文仍来自 OpenAlex。")
    else:
        st.success("实时结果 · 论文元数据与摘要来自 OpenAlex")
    if outcome.notice:
        st.info(outcome.notice)
    with st.expander("检索式与原始排序", expanded=False):
        for record in outcome.queries:
            st.write(f"**{record.branch_key}** · `{record.query}` · {record.error or f'返回 {len(record.returned_ids)} 条'}")
            if record.ranked_results:
                st.dataframe([
                    {"OpenAlex 原始排序": hit.get("raw_rank", hit.get("rank")), "相关性重排": hit.get("relevance_rank"), "论文 ID": hit.get("paper_id"), "状态": hit.get("status", "未评估"), "相关性规则分": hit.get("relevance_score"), "判定原因": hit.get("reason", "")}
                    for hit in record.ranked_results
                ], hide_index=True, width="stretch")
    if not outcome.papers:
        st.warning("没有可展示的论文，请调整检索式后重试。")
    for paper in outcome.papers:
        with st.container(border=True):
            st.markdown(f"#### {paper.title}")
            st.caption(f"年份：{paper.year or '未知'} · {'模拟数据' if paper.is_demo else 'OpenAlex'} · 命中分支：{', '.join(paper.found_by) or '无'}")
            st.write(paper.abstract or "OpenAlex 未提供摘要。")
            statuses = [hit for record in outcome.queries for hit in record.ranked_results if hit.get("paper_id") == paper.id]
            if statuses:
                best = max(statuses, key=lambda hit: {"Evidence Eligible": 2, "Relevant": 1, "Retrieved": 0}.get(hit.get("status"), -1))
                st.caption(f"检索状态：Retrieved → {best.get('status')} · {best.get('reason', '')}")
            if paper.abstract and not abstract_sufficient(paper.abstract) and not paper.is_demo:
                st.caption("此摘要过短，未纳入证据摘录与问题生成。")
            if paper.is_demo:
                st.caption("此卡片没有真实论文链接。")
            else:
                if paper.source_url:
                    st.link_button("论文原始来源", paper.source_url)
                if paper.openalex_url:
                    st.link_button("OpenAlex 记录", paper.openalex_url)
                st.caption("仅展示摘要与元数据；尚未核验全文。")


def show_report(report: ExplorationReport | None, outcome: SearchOutcome) -> None:
    st.subheader("5 · 初步研究版图与证据")
    if report is None:
        st.warning("没有真实摘要可用于证据整理；Demo 数据不会生成研究结论。")
        return
    st.caption(f"{report.scope} 生成方法：{report.method}；所有引文均取自 OpenAlex 摘要。")
    for reason in report.insufficiency_reasons:
        st.info(reason)
    st.markdown("**本轮检索覆盖的方向**")
    for row in report.landscape:
        st.write(f"{row.branch_title}：命中 {len(row.paper_ids)} 篇（按 OpenAlex 原始顺序记录）。")
        representative_titles = landscape_representatives(row, outcome)
        if representative_titles:
            st.caption("代表论文（原始排序前两篇）：" + "；".join(representative_titles))
    st.caption("以上是本轮样本的分布，不能代表整个研究领域的文献规模。")

    st.markdown("**研究现状：摘要中的原文表述**")
    if not report.current_work:
        st.info("本轮摘要没有足够清晰的现状摘录。")
    for item in report.current_work:
        st.markdown(f"> {item.quote}")
        st.caption(f"单篇摘要 · {item.paper_title} · {item.paper_id}")
        if item.source_url or item.openalex_url:
            st.link_button("查看来源", item.source_url or item.openalex_url)

    st.markdown("**有原文依据的局限：仅指被引论文的表述**")
    if not report.explicit_limitations:
        st.info("本轮没有找到足够明确的局限原文；不据此推断没有研究空白。")
    for item in report.explicit_limitations:
        st.markdown(f"> {item.quote}")
        st.caption(f"单篇摘要 · {item.paper_title} · {item.paper_id}")
        if item.source_url or item.openalex_url:
            st.link_button("查看来源", item.source_url or item.openalex_url)

    st.markdown("**候选 Research Questions · 系统推断，待验证**")
    if not report.candidate_questions:
        st.info("目前没有足够摘要依据生成候选问题。")
    for number, question in enumerate(report.candidate_questions, start=1):
        with st.container(border=True):
            st.write(f"**RQ {number}（待验证）** · {question.text}")
            st.caption(f"系统推断的潜在机会（待验证）：{getattr(question, 'opportunity', '需进一步检索验证。')}")
            st.caption(question.rationale)
            st.caption(f"启发来源：{', '.join(question.evidence_paper_ids)}")
            st.caption(f"下一步验证：{question.verification_step}")


st.set_page_config(page_title="Research Compass", page_icon="🧭", layout="wide")
st.title("Research Compass 🧭")
st.caption("从模糊兴趣到可选择的探索方向，再到可追溯的摘要证据。")

with st.container(border=True):
    st.markdown("**人工评测 · Human Evaluation**")
    st.caption("逐条标注 V0 / V1 的 35 篇检索结果，并查看 Precision@5、nDCG@5 与证据准入误差。")
    st.page_link(
        "pages/2_Evaluation.py",
        label="打开人工评测 Evaluation",
        icon="📝",
        use_container_width=True,
    )

for name, default in {
    "stage": "input", "interest": "", "intent": None, "plan_revision": 0,
    "planned_outcome": None, "baseline_outcome": None, "report": None,
    "selected_branches": [], "planner_mode": "规则方案 V1", "suggested_branches": [],
    "planner_metadata": None, "planner_notice": "",
}.items():
    st.session_state.setdefault(name, default)

with st.container(border=True):
    st.subheader("1 · 描述模糊研究兴趣")
    with st.form("interest_form"):
        interest = st.text_area("一句话就够了", value=st.session_state.interest or "AI for robot control")
        planner_mode = st.radio(
            "意图理解与查询规划", ["规则方案 V1", "Qwen V2"],
            index=0 if st.session_state.planner_mode == "规则方案 V1" else 1,
            horizontal=True,
            help="Qwen 仅用于理解意图和生成检索分支，不参与摘要证据综合；最多 5 次调用并受本地预算记录限制。",
        )
        submitted = st.form_submit_button("开始探索", type="primary")
    if submitted:
        if interest.strip():
            st.session_state.interest = interest.strip()
            st.session_state.planner_mode = planner_mode
            st.session_state.stage = "clarify"
            st.session_state.planned_outcome = None
            st.session_state.baseline_outcome = None
            st.session_state.report = None
            st.session_state.plan_revision += 1
            st.rerun()
        else:
            st.error("请先输入研究兴趣。")

if st.session_state.stage == "clarify":
    st.subheader("2 · 澄清研究意图（两题，可跳过）")
    with st.form("clarification_form"):
        goal = st.selectbox("你现在的主要研究目标是什么？", options=list(GOALS), format_func=GOALS.get)
        constraints = st.text_input("有什么研究约束或关注条件？（可留空）", placeholder="例如：低数据量、真实机器人、安全性")
        proceed = st.form_submit_button("生成探索方向", type="primary")
        skip = st.form_submit_button("不确定，跳过")
    if proceed or skip:
        clarified_goal = None if skip else goal
        clarified_constraints = "" if skip else constraints.strip()
        if st.session_state.planner_mode == "Qwen V2":
            try:
                intent, branches, metadata = plan_with_qwen(
                    st.session_state.interest, goal=clarified_goal,
                    clarified_constraints=clarified_constraints,
                )
                st.session_state.intent = intent
                st.session_state.suggested_branches = branches
                st.session_state.planner_metadata = metadata
                st.session_state.planner_notice = ""
            except QwenPlanningError as exc:
                intent = parse_intent(
                    st.session_state.interest, goal=clarified_goal,
                    clarified_constraints=clarified_constraints,
                )
                st.session_state.intent = intent
                st.session_state.suggested_branches = build_planned_branches(intent)
                st.session_state.planner_metadata = None
                st.session_state.planner_notice = f"Qwen 未生成方案，当前显示规则回退结果：{exc}"
        else:
            intent = parse_intent(
                st.session_state.interest,
                goal=clarified_goal,
                clarified_constraints=clarified_constraints,
            )
            st.session_state.intent = intent
            st.session_state.suggested_branches = build_planned_branches(intent)
            st.session_state.planner_metadata = None
            st.session_state.planner_notice = ""
        st.session_state.stage = "branches"
        st.rerun()

if st.session_state.stage in {"branches", "results"} and st.session_state.intent:
    intent: ResearchIntent = st.session_state.intent
    st.subheader("3 · 检查意图拆解并选择探索方向")
    if st.session_state.planner_notice:
        st.warning(st.session_state.planner_notice)
    elif st.session_state.planner_mode == "Qwen V2" and st.session_state.planner_metadata:
        metadata = st.session_state.planner_metadata
        st.caption(
            f"意图与查询由 {metadata['model']} 生成；未用于证据综合。"
            f"本次 {metadata.get('input_tokens')} 输入 / {metadata.get('output_tokens')} 输出 Token，"
            f"约 ¥{metadata.get('cost_cny')}；请确认或修改下方字段。"
        )
    else:
        st.caption("意图与查询由本地规则生成；可确认或修改。")
    st.caption("字段由本地中英文术语和关系规则解析，属于系统推断；请确认或修改。硬约束只记录用户明确输入的内容。")
    st.write(f"**系统理解的研究目标：** {intent.task or GOALS.get(intent.goal, intent.goal)}")
    st.write(f"**关系：** {intent.relationship or '尚未识别'}")
    st.write(f"**来源方法 → 目标方法：** {intent.source_method or '未识别'} → {intent.target_method or '未识别'}")
    st.dataframe([
        {"字段": label, "系统理解": value or "未识别", "来源判断": intent.field_provenance.get(key, "未标注")}
        for key, label, value in (
            ("domain", "领域", intent.domain),
            ("source_method_role", "来源方法", intent.source_method),
            ("target_method_role", "目标方法", intent.target_method),
            ("task", "研究目标", intent.task),
            ("relationship_direction", "方法关系", intent.relationship),
            ("constraints", "明确约束", "；".join(intent.explicit_constraints) or "无"),
        )
    ], hide_index=True, width="stretch")
    if intent.unconfirmed:
        st.caption("尚未确认的信息：" + "；".join(intent.unconfirmed))
    if intent.inferred:
        st.caption("系统推断：" + "；".join(intent.inferred))
    with st.form("intent_editor"):
        domain = st.text_input("研究领域（可修改）", value=intent.domain)
        source_method = st.text_input("来源方法（灵感来源，可留空）", value=intent.source_method)
        target_method = st.text_input("目标方法（拟探索，可留空）", value=intent.target_method)
        task = st.text_input("研究目标 / 任务", value=intent.task)
        relationship = st.text_input("方法关系", value=intent.relationship)
        edited_goal = st.selectbox("研究目标", list(GOALS), index=list(GOALS).index(intent.goal), format_func=GOALS.get)
        edited_constraints = st.text_input("约束 / 关注条件", value=intent.constraints)
        update_plan = st.form_submit_button("更新探索方向")
    if update_plan:
        if not domain.strip() and not target_method.strip():
            st.error("至少确认一个研究领域或方法。")
        else:
            st.session_state.intent = replace(
                intent, domain=domain.strip(), theme=domain.strip() or intent.theme,
                source_method=source_method.strip(), target_method=target_method.strip(),
                approach=", ".join(filter(None, (source_method.strip(), target_method.strip()))),
                task=task.strip(), relationship=relationship.strip(), goal=edited_goal,
                constraints=edited_constraints.strip(),
                explicit_constraints=(edited_constraints.strip(),) if edited_constraints.strip() else (),
                field_provenance={
                    **intent.field_provenance,
                    "domain": "用户确认/修改", "source_method_role": "用户确认/修改",
                    "target_method_role": "用户确认/修改", "task": "用户确认/修改",
                    "relationship_direction": "用户确认/修改",
                    "constraints": "用户明确输入" if edited_constraints.strip() else "无明确约束",
                    "goal": "用户确认/修改",
                },
            )
            st.session_state.suggested_branches = build_planned_branches(st.session_state.intent)
            st.session_state.planner_mode = "规则方案 V1"
            st.session_state.planner_metadata = None
            st.session_state.planner_notice = "已根据手动修改后的意图重新生成规则检索分支。"
            st.session_state.plan_revision += 1
            st.session_state.stage = "branches"
            st.rerun()

    suggested = st.session_state.suggested_branches or build_planned_branches(intent)
    revision = st.session_state.plan_revision
    with st.form("planned_branch_form"):
        chosen: list[SearchBranch] = []
        for branch in suggested:
            selected = st.checkbox(
                f"{branch.title} · {branch.purpose}",
                value=branch.key in default_planned_keys(intent.goal),
                key=f"select_{revision}_{branch.key}",
            )
            query = st.text_input("实际发送给 OpenAlex 的检索式", value=branch.query, key=f"query_{revision}_{branch.key}")
            if selected and query.strip():
                chosen.append(replace(branch, query=query.strip()))
        search_clicked = st.form_submit_button("检索并生成证据版图", type="primary")

    baseline_branches = build_branches(intent.original_interest, intent.constraints)
    with st.expander("Day 1 关键词扩展 Baseline（同轮独立检索）"):
        st.caption("保留原版 overview / methods / applications / challenges 关键词模板。结果与新方案分开保存，用于 Day 3 配对评测。")
        for branch in baseline_branches:
            st.code(f"{branch.key}: {branch.query}")

    if not api_key():
        st.warning("未加载 OPENALEX_API_KEY；匿名额度不足时会出现明确标记的 Demo 数据。")
    if search_clicked:
        if not chosen:
            st.error("请至少选择一个有检索式的探索方向。")
        else:
            with st.spinner("检索 OpenAlex，并分别保存新方案与 Baseline…"):
                key = api_key()
                planned = search_papers(chosen, key, intent=intent)
                baseline = search_papers(baseline_branches, key, intent=intent)
                report = build_report(planned, intent, {branch.key: branch.title for branch in chosen})
                st.session_state.planned_outcome = planned
                st.session_state.baseline_outcome = baseline
                st.session_state.report = report
                st.session_state.selected_branches = chosen
            st.session_state.stage = "results"
            st.rerun()

if st.session_state.stage == "results" and st.session_state.planned_outcome:
    planned: SearchOutcome = st.session_state.planned_outcome
    baseline: SearchOutcome = st.session_state.baseline_outcome
    planned_tab, baseline_tab = st.tabs(["新探索方案", "Day 1 Baseline"])
    with planned_tab:
        show_papers(planned, title="4 · 新探索方案的真实论文")
        show_report(st.session_state.report, planned)
    with baseline_tab:
        show_papers(baseline, title="Day 1 Baseline 的独立检索结果")

    trace = build_paired_trace(
        st.session_state.intent, st.session_state.selected_branches, planned,
        build_branches(st.session_state.interest, st.session_state.intent.constraints),
        baseline, st.session_state.report,
    )
    st.download_button(
        "下载配对检索与证据记录（JSON）",
        data=json.dumps(trace, ensure_ascii=False, indent=2),
        file_name="research-compass-day2-paired-trace.json",
        mime="application/json",
    )
