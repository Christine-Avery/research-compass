"""Page 2: select a path before making a live OpenAlex request."""

from dataclasses import replace
import os

from dotenv import load_dotenv
import streamlit as st

from research_compass.evidence import build_report
from research_compass.retrieval import search_papers
from research_compass.prototype_snapshot import activate_golden_snapshot
from research_compass.ui_theme import render_header


load_dotenv()
st.set_page_config(page_title="Research Path Explorer · Research Compass", page_icon="🧭", layout="wide")
activate_golden_snapshot(2)
render_header(2)
st.title("2 · Research Path Explorer")
st.caption("选择一条研究路径并查看真实文献结果。")
st.page_link("pages/1_Intent_Studio.py", label="← 修改研究意图")

intent = st.session_state.get("confirmed_intent")
branches = st.session_state.get("draft_paths", [])
if not intent or not branches:
    st.warning("请先在 AI Intent Studio 确认研究意图。")
    st.stop()

st.caption(f"已确认目标：{intent.task or intent.theme} · {intent.domain or '领域待确认'} · "
           f"{intent.source_method or '无来源方法'} → {intent.target_method or '无目标方法'}")
st.subheader("研究路径")
st.caption("选择后才会执行检索；已检索路径会从缓存切换，不重复请求。")
if st.session_state.get("golden_v2_next_card") and st.session_state.get("next_query_draft"):
    st.info(f"来自 Human-curated Golden Case v2 的方向 {st.session_state.golden_v2_next_card} 查询草稿。"
            "请在下方确认检索式并点击 OpenAlex 检索；新结果将标为 LIVE，历史 Snapshot 不会被改写。")

selected = st.session_state.get("selected_path")
path_columns = st.columns(min(3, max(1, len(branches[:3]))))
for index, branch in enumerate(branches[:3], start=1):
    with path_columns[index - 1]:
      with st.container(border=True):
        st.markdown(f"#### 路径 {index} · {branch.title}")
        st.write(branch.purpose or "探索该方法在研究领域中的相关工作。")
        st.code(branch.query, language=None)
        st.caption("重点方法：" + (branch.focus_method or "由检索式决定") + " · 摘要筛选要求：" +
                   ("、".join(branch.required_methods) or "研究主题"))
        cached_path = st.session_state.get("path_outcomes", {}).get(branch.key)
        label = ("当前已选路径" if selected == branch.key else
                 "切换到已检索路径" if cached_path else "选择并检索这条路径")
        if st.button(label,
                     key=f"choose_{index}", type="primary" if selected == branch.key else "secondary",
                     disabled=selected == branch.key):
            if cached_path and selected != branch.key:
                if isinstance(cached_path, tuple):
                    outcome, report = cached_path
                else:
                    outcome = cached_path
                    report = build_report(outcome, intent, {branch.key: branch.title})
                    st.session_state.path_outcomes[branch.key] = (outcome, report)
            else:
                key = os.getenv("OPENALEX_API_KEY", "").strip()
                if not key:
                    try:
                        key = str(st.secrets.get("OPENALEX_API_KEY", "")).strip()
                    except (FileNotFoundError, KeyError):
                        key = ""
                with st.spinner("OpenAlex 正在检索所选路径……"):
                    outcome = search_papers([branch], key or None, intent=intent)
                    report = build_report(outcome, intent, {branch.key: branch.title})
                st.session_state.setdefault("path_outcomes", {})[branch.key] = (outcome, report)
            st.session_state.selected_path = branch.key
            st.session_state.selected_outcome = outcome
            st.session_state.selected_report = report
            st.rerun()

if selected:
    cached = st.session_state.get("path_outcomes", {}).get(selected)
    if cached:
        branch = next((item for item in branches if item.key == selected), None)
        if isinstance(cached, tuple):
            outcome, report = cached
        else:
            outcome = cached
            report = build_report(outcome, intent, {branch.key: branch.title} if branch else {})
            st.session_state.path_outcomes[selected] = (outcome, report)
        if branch:
            with st.expander("修改检索式并继续探索", expanded=bool(st.session_state.get("next_query_draft"))):
                with st.form("query_revision"):
                    revised_query = st.text_input("下一轮英文检索式", value=st.session_state.get("next_query_draft") or branch.query)
                    run_revised = st.form_submit_button("按此检索式执行 OpenAlex 检索")
                if run_revised:
                    if not revised_query.strip():
                        st.error("请输入检索式。")
                    else:
                        revised_branch = replace(branch, query=revised_query.strip())
                        key = os.getenv("OPENALEX_API_KEY", "").strip()
                        if not key:
                            try:
                                key = str(st.secrets.get("OPENALEX_API_KEY", "")).strip()
                            except (FileNotFoundError, KeyError):
                                key = ""
                        with st.spinner("执行下一轮 OpenAlex 检索……"):
                            new_outcome = search_papers([revised_branch], key or None, intent=intent)
                            new_report = build_report(new_outcome, intent, {revised_branch.key: revised_branch.title})
                        st.session_state.draft_paths = [revised_branch if item.key == branch.key else item for item in branches]
                        st.session_state.path_outcomes[branch.key] = (new_outcome, new_report)
                        st.session_state.selected_outcome = new_outcome
                        st.session_state.selected_report = new_report
                        st.session_state.pop("next_query_draft", None)
                        st.session_state.pop("golden_v2_next_card", None)
                        st.rerun()
        st.divider()
        st.subheader(f"所选路径的论文 · {branch.title if branch else selected}")
        if outcome.mode == "demo":
            st.error("DEMO 回退：OpenAlex 检索失败；以下不是实际论文，不会进入证据页。")
        elif outcome.mode == "snapshot":
            st.info("历史 Snapshot · 以下为已保存的真实 OpenAlex 记录；本次未发起实时检索。")
        elif outcome.mode == "partial":
            st.warning("部分实时结果；具体失败请看检索记录。")
        else:
            st.success("LIVE · 来自 OpenAlex 的真实论文元数据及摘要")
        if outcome.notice and outcome.mode != "snapshot":
            st.info(outcome.notice)
        for record in outcome.queries:
            st.caption(f"英文查询：{record.query} · 返回 {len(record.returned_ids)} 条 · {record.error or '请求成功'}")
        if not outcome.papers:
            st.warning("没有命中论文。请调整路径或查询。")
        for paper_index, paper in enumerate(outcome.papers):
            hits = [hit for record in outcome.queries for hit in record.ranked_results if hit.get("paper_id") == paper.id]
            hit = hits[0] if hits else {}
            with st.container(border=True):
                st.markdown(f"#### {paper.title}")
                st.caption(f"{paper.year or '年份未知'} · 原始排名 {hit.get('raw_rank', 'N/A')} · "
                           f"{hit.get('status', '未评估')} · ID: {paper.id}")
                with st.expander("查看摘要", expanded=paper_index == 0):
                    st.write(paper.abstract or "OpenAlex 未提供摘要。")
                st.caption("相关性与证据准入解释：" + hit.get("reason", "无规则判定；不可作为证据"))
                if not paper.is_demo:
                    if paper.source_url:
                        st.link_button("论文来源", paper.source_url)
                    if paper.openalex_url:
                        st.link_button("OpenAlex 记录", paper.openalex_url)
                    st.caption("仅据摘要筛选；全文尚未核验。")
        if outcome.mode != "demo":
            st.page_link("pages/3_Evidence_Next.py", label="查看 Evidence & Next Steps →", icon="🔎")
