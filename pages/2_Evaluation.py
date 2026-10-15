from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

import streamlit as st

from research_compass.human_eval import calculate_metrics, parse_relevance, parse_yes_no, row_key


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "evaluation" / "runs" / "v3_20261014"
SOURCE_CSV = RUN_DIR / "live_openalex_human_review.csv"
GOLDEN_JSON = RUN_DIR / "live_openalex_golden.json"
TRACE_JSON = ROOT / "evaluation" / "cases" / "badcase_001" / "original_trace.json"
LABELS_CSV = Path(os.getenv("RESEARCH_COMPASS_HUMAN_LABELS_PATH", str(RUN_DIR / "human_labels.csv")))
LABEL_FIELDS = ["review_id", "human_relevance_label", "human_evidence_eligible_label", "evidence_reason", "claim_support_label", "reviewer", "notes", "review_status"]
HISTORY_READ_ONLY = LABELS_CSV.resolve() == (RUN_DIR / "human_labels.csv").resolve() and LABELS_CSV.exists()
PUBLIC_READ_ONLY = os.getenv("PUBLIC_DEPLOYMENT", "false").lower() == "true"

st.set_page_config(page_title="Research Compass · Evaluation", page_icon="🧭", layout="wide")
st.title("Human Evaluation")
st.page_link("pages/1_Intent_Studio.py", label="返回 Research Compass 首页", icon="🏠")
st.caption("展示 V0 / V1 的历史人工评测结果。" if PUBLIC_READ_ONLY else
           "对 V0 / V1 的检索结果进行人工判断。所有标签由评审者填写，不会自动生成。")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def context_data() -> tuple[str, dict[tuple[str, str], str]]:
    trace = json.loads(TRACE_JSON.read_text(encoding="utf-8-sig"))
    golden = json.loads(GOLDEN_JSON.read_text(encoding="utf-8-sig"))
    queries: dict[tuple[str, str], str] = {}
    for version, strategy in golden.get("strategies", {}).items():
        for item in strategy.get("search", {}).get("queries", []):
            queries[(version, str(item.get("branch_key", "")))] = str(item.get("query", ""))
    return str(trace.get("interest", "")), queries


def load_rows() -> list[dict[str, Any]]:
    source_rows = read_csv(SOURCE_CSV)
    saved_by_id: dict[str, dict[str, str]] = {}
    if LABELS_CSV.exists():
        saved_by_id = {row.get("review_id", ""): row for row in read_csv(LABELS_CSV)}
    user_query, queries = context_data()
    combined: list[dict[str, Any]] = []
    for i, source in enumerate(source_rows):
        record: dict[str, Any] = dict(source)
        rid = row_key(source, i)
        saved = saved_by_id.get(rid, {})
        record["review_id"] = rid
        record["raw_user_query"] = user_query
        record["branch_query"] = queries.get((source.get("version", ""), source.get("branch", "")), "")
        record["openalex_url"] = source.get("paper_id", "") if str(source.get("paper_id", "")).startswith("https://openalex.org/") else ""
        doi = str(source.get("doi", "")).strip()
        record["source_url"] = doi if doi.startswith("http") else (f"https://doi.org/{doi}" if doi else record["openalex_url"])
        for field in LABEL_FIELDS:
            record[field] = saved.get(field, record.get(field, ""))
        combined.append(record)
    return combined


def save_rows(rows: list[dict[str, Any]]) -> None:
    if PUBLIC_READ_ONLY:
        raise PermissionError("Public Evaluation is read-only")
    if HISTORY_READ_ONLY:
        raise PermissionError("Historical human_labels.csv is read-only; use targeted review")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    source_fields = list(read_csv(SOURCE_CSV)[0].keys())
    fields = list(dict.fromkeys([*source_fields, *LABEL_FIELDS]))
    with LABELS_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if PUBLIC_READ_ONLY:
    st.info("公网评测仅展示已保存的历史标签与指标；匿名访客不能保存或定向复核。")
    review_mode = "历史评测（只读）"
else:
    review_mode = st.selectbox("评测视图", ["历史评测（只读）", "定向复核 7 条"])
if review_mode == "定向复核 7 条":
    from research_compass.targeted_review_ui import render

    original_query, branch_queries = context_data()
    render(
        RUN_DIR / "human_labels.csv",
        ROOT / "evaluation" / "reports" / "targeted_review_v1_20261014",
        original_query,
        branch_queries,
    )
    st.stop()

if HISTORY_READ_ONLY and not PUBLIC_READ_ONLY:
    st.info("历史 human_labels.csv 已冻结为 V1 标注快照。请切换到“定向复核 7 条”保存修正版标签。")

rows = load_rows()
if len(rows) != 35:
    st.error(f"期望读取 35 条来源记录，实际读取 {len(rows)} 条。请检查只读来源 CSV。")
    st.stop()

completed = sum(parse_relevance(r.get("human_relevance_label")) is not None and parse_yes_no(r.get("human_evidence_eligible_label")) is not None for r in rows)
st.progress(completed / len(rows), text=f"已完成双项标注：{completed}/{len(rows)} 条；原始记录：{len(rows)} 条")
if "human_eval_index" not in st.session_state:
    st.session_state.human_eval_index = next((i for i, r in enumerate(rows) if not (parse_relevance(r.get("human_relevance_label")) is not None and parse_yes_no(r.get("human_evidence_eligible_label")) is not None)), 0)
idx = max(0, min(int(st.session_state.human_eval_index), len(rows) - 1))
row = rows[idx]

st.subheader(f"记录 {idx + 1} / {len(rows)} · {row['version']} · {row['branch']} · 原始排名 {row['raw_rank']}")
with st.expander("原始研究 Query 与该分支实际检索式", expanded=True):
    st.markdown("**用户原始 Query**")
    st.write(row.get("raw_user_query") or "来源 Trace 未提供")
    st.markdown("**该分支实际检索式**")
    st.code(row.get("branch_query") or "Golden 运行记录中未找到对应检索式")
    st.caption(f"方案：{'V0 Day 1 Baseline' if row['version'] == 'V0_Day1_Baseline' else 'V1 Optimized Rules'} · 分支：{row['branch']} · raw rank：{row['raw_rank']} · relevance rank：{row.get('relevance_rank', '')}")

st.markdown(f"### {row.get('title') or '(无标题)'}")
st.write(row.get("abstract") or "来源记录没有摘要。")
link_col1, link_col2 = st.columns(2)
if row.get("source_url"):
    link_col1.link_button("论文 / DOI 来源", row["source_url"])
if row.get("openalex_url"):
    link_col2.link_button("OpenAlex 记录", row["openalex_url"])

def relevance_display(value: Any) -> str:
    parsed = parse_relevance(value)
    return "未标注" if parsed is None else f"{parsed} — {['不相关', '部分相关', '高度相关'][parsed]}"


rel_options = ["未标注", "0 — 不相关", "1 — 部分相关", "2 — 高度相关"]
rel_default = relevance_display(row.get("human_relevance_label"))
ev_options = ["未标注", "是 — 适合进入 Evidence Generation", "否 — 不适合进入 Evidence Generation"]
ev_value = parse_yes_no(row.get("human_evidence_eligible_label"))
ev_default = "未标注" if ev_value is None else (ev_options[1] if ev_value else ev_options[2])

with st.form(f"review_form_{idx}"):
    relevance_choice = st.radio("人工相关性（与证据准入分别判断）", rel_options, index=rel_options.index(rel_default), horizontal=True, disabled=PUBLIC_READ_ONLY)
    evidence_choice = st.radio("是否适合进入 Evidence Generation", ev_options, index=ev_options.index(ev_default), disabled=PUBLIC_READ_ONLY)
    evidence_reason = st.text_area("证据准入判断原因（请说明摘要/主题依据）", value=row.get("evidence_reason", ""), height=100, disabled=PUBLIC_READ_ONLY)
    reviewer = st.text_input("评审者（可选）", value=row.get("reviewer", ""), disabled=PUBLIC_READ_ONLY)
    notes = st.text_area("其他备注（可选）", value=row.get("notes", ""), height=70, disabled=PUBLIC_READ_ONLY)
    buttons = st.columns(4)
    save_only = buttons[0].form_submit_button("保存进度", type="primary", disabled=HISTORY_READ_ONLY or PUBLIC_READ_ONLY)
    previous = buttons[1].form_submit_button("保存并上一条", disabled=HISTORY_READ_ONLY or PUBLIC_READ_ONLY)
    following = buttons[2].form_submit_button("保存并下一条", disabled=HISTORY_READ_ONLY or PUBLIC_READ_ONLY)
    skip = buttons[3].form_submit_button("跳过（不保存本条）", disabled=PUBLIC_READ_ONLY)

if save_only or previous or following:
    row["human_relevance_label"] = "" if relevance_choice == "未标注" else relevance_choice[0]
    row["human_evidence_eligible_label"] = "" if evidence_choice == "未标注" else ("yes" if evidence_choice.startswith("是") else "no")
    row["evidence_reason"] = evidence_reason.strip()
    row["reviewer"] = reviewer.strip()
    row["notes"] = notes.strip()
    row["review_status"] = "complete" if parse_relevance(row["human_relevance_label"]) is not None and parse_yes_no(row["human_evidence_eligible_label"]) is not None else "in_progress"
    rows[idx] = row
    save_rows(rows)
    st.success(f"已保存到独立标注文件（{len(rows)} 条记录）。")
    if previous:
        st.session_state.human_eval_index = max(0, idx - 1)
        st.rerun()
    if following:
        st.session_state.human_eval_index = min(len(rows) - 1, idx + 1)
        st.rerun()
if skip:
    st.session_state.human_eval_index = min(len(rows) - 1, idx + 1)
    st.rerun()

nav_left, nav_mid, nav_right = st.columns([1, 2, 1])
if nav_left.button("← 上一条", disabled=idx == 0):
    st.session_state.human_eval_index = idx - 1
    st.rerun()
target = nav_mid.number_input("记录序号", min_value=1, max_value=len(rows), value=idx + 1, step=1, key="jump_number")
if nav_mid.button("跳转", key="jump_go"):
    st.session_state.human_eval_index = int(target) - 1
    st.rerun()
if nav_right.button("下一条 →", disabled=idx >= len(rows) - 1):
    st.session_state.human_eval_index = idx + 1
    st.rerun()

st.divider()
st.header("标注质量与 V0 / V1 指标")
st.caption("仅基于已保存的人类标签。未标注项不按不相关处理。Precision@5 和 nDCG@5 仅纳入该分支 top-5 全部完成相关性标注的分支，并对完整分支做宏平均。相关阈值：1（部分相关）及以上视为相关；nDCG 使用 0/1/2 分级增益 0/1/3。")
metrics = calculate_metrics(rows)
metric_rows = []
for version, values in metrics["versions"].items():
    metric_rows.append({
        "方案": "V0" if version == "V0_Day1_Baseline" else "V1",
        "已完成 top-5 分支 / 全部分支": f"{values['complete_top_k_branches']}/{values['branch_count']}",
        "Precision@5（完整分支宏平均）": values["precision_at_k"],
        "nDCG@5（完整分支宏平均）": values["ndcg_at_k"],
        "无关证据率（分子/系统准入且已标注）": f"{values['irrelevant_evidence_numerator']}/{values['irrelevant_evidence_denominator']}" if values["irrelevant_evidence_denominator"] else "N/A（该方案无准入记录）",
    })
st.dataframe(metric_rows, hide_index=True, width="stretch")
v1 = metrics["versions"].get("V1_Optimized_Rules", {}).get("evidence_gate")
if v1:
    st.subheader("V1 Evidence Gate 误收录 / 误拒绝审计")
    st.caption(f"分母：已标注人工准入标签的 V1 记录 {v1['labeled_denominator']} 条。系统准入预测为 rule_status=Evidence Eligible；人工 yes/no 为参照。V0 无系统 Evidence Gate，不计算。")
    c1, c2 = st.columns(2)
    c1.metric("误收录（系统准入 / 人工否）", v1["false_accept_count"])
    c2.metric("误拒绝（系统未准入 / 人工是）", v1["false_reject_count"])
    with st.expander("查看误差记录"):
        st.write("误收录")
        st.dataframe(v1["false_accepts"], hide_index=True, width="stretch")
        st.write("误拒绝")
        st.dataframe(v1["false_rejects"], hide_index=True, width="stretch")

if LABELS_CSV.exists():
    st.download_button("下载当前独立标注 CSV", data=LABELS_CSV.read_bytes(), file_name="human_labels.csv", mime="text/csv")
else:
    st.info("尚无已保存标注。点击“保存进度”后，将在独立文件中创建包含全部 35 条来源记录的标注副本。")

with st.expander("指标口径与标签说明"):
    st.markdown("""
- **Precision@5**：每个完整分支中，相关性 ≥1 的论文数 / 5；各完整分支宏平均。若不足 5 条返回但该分支全部返回项均已标注，缺少的名次按未命中计入固定 K=5。
- **nDCG@5**：每个完整分支按原始排名计算 DCG，相关性 0/1/2 对应 gain 0/1/3，再除以理想排序 IDCG；各完整分支宏平均。
- **无关证据率**：系统标记为 Evidence Eligible、且相关性已标注的论文中，相关性为 0 的数量 / 这类系统准入记录总数。未标注相关性的系统准入记录排除；若方案没有 Evidence Gate / 准入记录（当前 V0），显示 N/A。
- **误收录 / 误拒绝**：仅对 V1 的规则准入结果，与人工 Evidence Generation yes/no 对照；无人工准入判断的记录排除。
- 每条来源记录的 review_id 包含方案、分支、原始排名、论文 ID 和行序号；跨分支重复论文保持独立判断。
""")
