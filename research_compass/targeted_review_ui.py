"""Streamlit controls for a small, human-decided annotation correction queue."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from research_compass.human_eval import parse_relevance, parse_yes_no
from research_compass.targeted_review import (
    EDIT_FIELDS, candidates, gate_metrics, load_reviewed, save_review, snapshot_rows,
)
from research_compass.targeted_report import write_report


def render(snapshot_path: Path, output_dir: Path, user_query: str, queries: dict[tuple[str, str], str]) -> None:
    if os.getenv("PUBLIC_DEPLOYMENT", "false").lower() == "true":
        st.info("Public Evaluation is read-only. Human annotation and correction are disabled.")
        return
    st.subheader("定向标注复核")
    st.info(
        "评测负样本仍保留在检索评测集，用来检查系统能否排除无关论文；"
        "它不应仅因是负样本而进入 Evidence Generation。"
        "请分别判断主题相关性，以及摘要是否适合作为本研究问题的事实或局限证据。"
    )
    st.caption("仅复核 7 条指定记录。历史 human_labels.csv 只读；每次保存另写修正版 CSV 和带时间的修改事件。所有选项由您判断。")
    baseline = snapshot_rows(snapshot_path)
    chosen = candidates(baseline)
    if len(chosen) != 7:
        st.error(f"预期 7 条定向复核记录，实际 {len(chosen)} 条；请检查历史快照。")
        return
    events_dir = output_dir / "changes"
    rows, reviewed = load_reviewed(snapshot_path, events_dir)
    by_id = {row["review_id"]: row for row in rows}
    st.progress(len(reviewed & {rid for rid, _ in chosen}) / len(chosen), text=f"已人工复核 {len(reviewed & {rid for rid, _ in chosen})}/{len(chosen)} 条")
    if "targeted_review_index" not in st.session_state:
        st.session_state.targeted_review_index = 0
    idx = max(0, min(int(st.session_state.targeted_review_index), len(chosen) - 1))
    rid, category = chosen[idx]
    row = by_id[rid]
    original = next(record for record in baseline if record["review_id"] == rid)

    st.markdown(f"### {idx + 1}/7 · {category}")
    st.caption(f"{row['version']} · {row['branch']} · 原始排名 {row['raw_rank']} · 系统状态 {row['rule_status']}")
    st.write("**原始用户意图**", user_query)
    with st.expander("该分支实际检索式"):
        st.code(queries.get((row["version"], row["branch"]), "未找到检索式"))
    st.markdown(f"**{row['title']}**")
    st.write(row.get("abstract") or "来源记录无摘要")
    st.link_button("OpenAlex 来源", row["paper_id"])
    if row.get("doi"):
        doi = row["doi"]
        st.link_button("论文 DOI", doi if doi.startswith("http") else f"https://doi.org/{doi}")
    st.caption(
        f"历史标签：相关性 {original.get('human_relevance_label') or '空'}；"
        f"证据准入 {original.get('human_evidence_eligible_label') or '空'}。"
        " 历史值始终保留在只读快照中。"
    )

    before = {field: row.get(field, "") for field in EDIT_FIELDS}
    rel_options = ["0 — 不相关", "1 — 部分相关", "2 — 高度相关"]
    current_rel = parse_relevance(row.get("human_relevance_label"))
    ev_options = ["未判断", "是 — 适合进入 Evidence Generation", "否 — 不适合进入 Evidence Generation"]
    current_ev = parse_yes_no(row.get("human_evidence_eligible_label"))
    ev_index = 0 if current_ev is None else (1 if current_ev else 2)
    with st.form(f"targeted_form_{idx}"):
        rel_choice = st.radio("人工相关性", rel_options, index=current_rel if current_rel is not None else 0)
        ev_choice = st.radio("摘要是否适合进入 Evidence Generation", ev_options, index=ev_index)
        evidence_reason = st.text_area("判断依据：摘要能支持什么、不能支持什么", value=row.get("evidence_reason", ""), height=90)
        change_reason = st.text_area("本次复核原因（必填；维持原判断时也请说明）", height=80)
        reviewer = st.text_input("复核者", value=row.get("reviewer", ""))
        save = st.form_submit_button("保存本条复核", type="primary")
    if save:
        evidence = "" if ev_choice == ev_options[0] else ("yes" if ev_choice == ev_options[1] else "no")
        after = {
            "human_relevance_label": rel_choice[0],
            "human_evidence_eligible_label": evidence,
            "evidence_reason": evidence_reason.strip(),
            "reviewer": reviewer.strip(),
            "review_status": "complete" if evidence else "in_progress",
        }
        try:
            event = save_review(snapshot_path, events_dir, output_dir / "human_labels_reviewed.csv", rid, before, after, change_reason)
        except ValueError as exc:
            st.error(str(exc))
        else:
            write_report(snapshot_path, output_dir)
            st.success(f"已保存 {event['timestamp_utc']}；修改前后数值及原因已记入独立事件。")
            rows, reviewed = load_reviewed(snapshot_path, events_dir)

    left, middle, right = st.columns([1, 2, 1])
    if left.button("上一条", disabled=idx == 0):
        st.session_state.targeted_review_index = idx - 1
        st.rerun()
    target = middle.selectbox(
        "跳转到复核条目",
        range(len(chosen)),
        index=idx,
        format_func=lambda i: f"{i + 1}. {chosen[i][1]} · {by_id[chosen[i][0]]['title'][:50]}" + (" ✓" if chosen[i][0] in reviewed else ""),
    )
    if middle.button("跳转", key="targeted_jump"):
        st.session_state.targeted_review_index = int(target)
        st.rerun()
    if right.button("下一条", disabled=idx == len(chosen) - 1):
        st.session_state.targeted_review_index = idx + 1
        st.rerun()

    st.divider()
    st.subheader("当前修正版指标")
    result = gate_metrics(rows)
    st.caption(
        "相关性 ≥1 计命中；P@5 与 nDCG@5 按完整分支求平均。"
        f" V1 准入判断已填 {result['evidence_judged']}/{result['v1_rows']} 条；"
        "未填项不当作否，复核未完成前这些 Gate 指标仅为阶段性结果。"
    )
    st.dataframe([
        {"方案": "V0 历史", "P@5": result["v0"]["precision_at_k"], "nDCG@5": result["v0"]["ndcg_at_k"]},
        {"方案": "V1 修正版", "P@5": result["v1"]["precision_at_k"], "nDCG@5": result["v1"]["ndcg_at_k"]},
    ], hide_index=True, width="stretch")
    st.write(f"V1 Gate：TP={result['tp']}，FP={result['fp']}，FN={result['fn']}，TN={result['tn']}")
    st.write(
        f"V1 Gate Precision={result['tp']}/{result['precision_denominator']}（{result['precision']:.1%}）"
        if result["precision"] is not None else "V1 Gate Precision=N/A（无系统准入）"
    )
    st.write(
        f"V1 Gate Recall={result['tp']}/{result['recall_denominator']}（{result['recall']:.1%}）"
        if result["recall"] is not None else "V1 Gate Recall=N/A（无人工应准入论文）"
    )
    if len(reviewed & {rid for rid, _ in chosen}) == len(chosen) and result["evidence_missing"] == 0:
        st.success("7 条定向复核和全部 Evidence Eligibility 判断已完成；最终修正版报告已生成。")
    else:
        st.warning("尚未完成全部定向复核；最终修正版报告与指标变化须等待人工保存。")
    if (output_dir / "report.md").exists():
        st.download_button("下载当前复核报告", (output_dir / "report.md").read_bytes(), file_name="targeted_review_report.md", mime="text/markdown")
