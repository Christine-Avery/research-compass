"""Page 3: abstract-grounded facts, tentative questions, and next searches."""

import streamlit as st

from research_compass.evidence import build_report
from research_compass.planning import build_planned_branches
from research_compass.prototype_snapshot import activate_golden_snapshot
from research_compass.ui_theme import render_header


st.set_page_config(page_title="Evidence & Next Steps · Research Compass", page_icon="🧭", layout="wide")
activate_golden_snapshot(3)
render_header(3)
st.title("从证据走向下一步")
st.page_link("pages/2_Path_Explorer.py", label="← 切换研究路径")

intent = st.session_state.get("confirmed_intent")
outcome = st.session_state.get("selected_outcome")
report = st.session_state.get("selected_report")
branches = st.session_state.get("draft_paths", [])
selected = st.session_state.get("selected_path")
branch = next((item for item in branches if item.key == selected), None)
if not intent or not outcome:
    st.warning("请先确认意图并检索一条研究路径。")
    st.stop()

golden_v2_mode = (outcome.mode == "snapshot"
                  and st.session_state.get("_prototype_snapshot_loaded")
                  and st.session_state.get("golden_v2_mode"))
if golden_v2_mode:
    from research_compass.golden_v2 import load_golden_v2_path
    from research_compass.golden_v2_ui import render_golden_v2_card

    path_id = st.session_state.get("selected_path_id") or selected
    current_branch = next((item for item in branches if item.key == path_id), None)
    cached = st.session_state.get("path_outcomes", {}).get(path_id)
    if not current_branch or not cached:
        st.warning("当前研究路径的历史检索结果不可用，请返回路径页重新选择。")
        st.stop()
    current_outcome = cached[0] if isinstance(cached, tuple) else cached
    if current_outcome.mode != "snapshot":
        st.warning("当前路径已进入新一轮检索，请使用实时结果的证据页。")
        st.stop()
    try:
        mapping, card = load_golden_v2_path(path_id)
    except (OSError, ValueError, KeyError, TypeError):
        st.error("演示证据无法核验，请返回路径页。")
        st.stop()
    st.session_state.selected_path = path_id
    st.session_state.selected_outcome = current_outcome
    st.query_params["prototype_snapshot"] = "golden"
    st.query_params["opportunities"] = "v2"
    st.query_params["path"] = path_id
    render_golden_v2_card(mapping, card, current_branch.title)
    st.stop()

# Local extraction is deterministic and free; refresh it from the stored papers
# without repeating an OpenAlex or Qwen request.
report = build_report(outcome, intent, {branch.key: branch.title} if branch else {})
st.session_state.selected_report = report

if outcome.mode == "demo" or report is None:
    st.error("当前只有明确标记的 Demo 回退数据；不能据此生成研究证据或问题。")
    st.stop()

st.caption("当前路径：" + (branch.title if branch else selected or "未知") + " · 来源：OpenAlex 摘要；全文未核验")
if outcome.mode == "snapshot":
    st.info("历史 Snapshot · 本页内容来自已保存的 OpenAlex 真实记录和摘要抽取；未进行实时 API 调用。")
st.subheader("Evidence Landscape")
st.caption("先区分三层：Retrieved 是检索返回；Relevant 是主题相关；Evidence Eligible 是摘要和来源满足准入条件。事实性陈述还需逐句对应摘要。")
for row in report.landscape:
    with st.container(border=True):
        st.write(f"**{row.branch_title}** · Retrieved {row.retrieved_count} / Relevant {row.relevant_count} / "
                 f"Evidence Eligible {row.evidence_eligible_count}")
        if row.paper_ids:
            st.caption("准入论文 ID：")
            for paper_id in row.paper_ids:
                st.code(paper_id, language=None)
        elif row.exclusions:
            st.caption("未准入原因示例：" + "；".join(row.exclusions[:2]))

for reason in report.insufficiency_reasons:
    st.info(reason)

def _show_quotes(title, quotes):
    st.markdown(f"**{title}**")
    if not quotes:
        st.caption("本轮没有足够的摘要原文支持此类声明。")
    for item in quotes:
        with st.container(border=True):
            st.markdown(f"> {item.quote}")
            st.caption(f"原文摘要句子 · {item.paper_title} · {item.paper_id} · 仅支持此句的陈述")
            if item.source_url or item.openalex_url:
                st.link_button("核查论文来源", item.source_url or item.openalex_url)

_show_quotes("摘要支持的研究现状", report.current_work)
_show_quotes("摘要明确表述的局限", report.explicit_limitations)

st.subheader("Candidate Research Questions · 待验证假设")
st.caption("以下由本地规则基于合格摘要提出，属于待验证假设；未调用 Qwen 生成问题，也不证明研究空白。")
if not report.candidate_questions:
    st.info("目前没有足够合格证据，不生成候选研究问题。")
for index, question in enumerate(report.candidate_questions, start=1):
    with st.container(border=True):
        st.write(f"**RQ {index} · 待验证**：{question.text}")
        st.caption(question.rationale)
        st.caption("启发论文 ID：" + "、".join(question.evidence_paper_ids))
        st.write("验证步骤：" + question.verification_step)

st.subheader("Next Search · 下一轮检索")
st.caption("非 LLM 建议；可编辑后返回路径页执行新一轮 OpenAlex 检索。")
suggested = branch.query if branch else ""
if not report.current_work and not report.explicit_limitations:
    alternatives = build_planned_branches(intent)
    target = next((item for item in alternatives if item.focus_method == intent.target_method), None)
    suggested = target.query if target else (alternatives[0].query if alternatives else suggested)
    st.info("当前路径缺少支持性摘要句子。下一轮先使用较短的领域 + 方法检索式，避免把返回数量当作证据。")
if branch:
    next_query = st.text_input("下一轮英文检索式", value=suggested, key=f"next_query_{selected}")
    if st.button("带着检索式继续探索", type="primary"):
        if next_query.strip():
            st.session_state.next_query_draft = next_query.strip()
            st.switch_page("pages/2_Path_Explorer.py")
        else:
            st.error("请先输入下一轮检索式。")

st.subheader("Research Plan Summary")
st.caption("点击代码块右上角复制。仅记录已确认意图、实际检索元数据和原文摘要；不补写未核实结论。")
lines = [
    "# Research Plan Summary",
    f"- 原始兴趣：{intent.original_interest}",
    f"- 已确认意图：{intent.task or intent.theme}; 领域 {intent.domain or '待确认'}; "
    f"{intent.source_method or '无来源方法'} → {intent.target_method or '无目标方法'}",
    f"- 明确约束：{'；'.join(intent.explicit_constraints) or '无'}",
    f"- 规划来源：{st.session_state.get('plan_source', '未记录')}",
    f"- 当前路径：{branch.title if branch else selected or '未知'}",
    f"- 实际查询：{outcome.queries[0].query if outcome.queries else '未记录'}",
    f"- 检索时间：{outcome.retrieved_at}; 数据状态：{outcome.mode}",
    f"- 证据门槛：Retrieved {sum(row.retrieved_count for row in report.landscape)}, "
    f"Relevant {sum(row.relevant_count for row in report.landscape)}, "
    f"Evidence Eligible {sum(row.evidence_eligible_count for row in report.landscape)}",
    "- 摘要支持的事实与局限：",
]
quotes = [*report.current_work, *report.explicit_limitations]
if quotes:
    for item in quotes:
        lines.append(f"  - [{item.kind}] {item.quote} — {item.paper_id} ({item.source_url or item.openalex_url})")
else:
    lines.append("  - 本轮没有通过具体声明支持校验的摘要句子。")
lines.append("- 候选研究问题（待验证）：")
if report.candidate_questions:
    for item in report.candidate_questions:
        lines.append(f"  - {item.text} 来源 ID: {', '.join(item.evidence_paper_ids)}")
else:
    lines.append("  - 无；证据不足时不生成。")
lines.append(f"- 下一轮检索建议（本地规则，可修改）：{next_query if branch else suggested}")
summary = "\n".join(lines)
st.code(summary, language="markdown")
st.download_button("下载 Research Plan Summary", summary, file_name="research-plan-summary.md", mime="text/markdown")
st.page_link("pages/2_Path_Explorer.py", label="返回研究路径，继续探索 →", icon="🧭")
