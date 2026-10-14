"""Page 1: one paid planning call, editable intent, and an explicit fallback."""

from dataclasses import replace
import json
import os

from dotenv import load_dotenv
import streamlit as st

from research_compass.planning import ResearchIntent, build_planned_branches, normalize_concepts, parse_intent
from research_compass.prototype_snapshot import activate_golden_snapshot, load_golden_snapshot
from research_compass.public_budget import public_budget_enabled
from research_compass.qwen_planning import LEDGER, MAX_CALLS, QwenPlanningError, plan_with_qwen
from research_compass.ui_theme import render_header


load_dotenv()
st.set_page_config(page_title="AI Intent Studio · Research Compass", page_icon="🧭", layout="wide")
activate_golden_snapshot(1)
render_header(1)


def _deployment_secrets() -> None:
    """Accept private Streamlit Secrets without displaying or persisting them."""
    for name in ("DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "DASHSCOPE_MODEL"):
        if not os.getenv(name):
            try:
                value = st.secrets.get(name)
            except (FileNotFoundError, KeyError):
                value = None
            if value:
                os.environ[name] = str(value)


def _needs_one_question(intent: ResearchIntent) -> bool:
    return not intent.domain or bool(intent.source_method and intent.target_method and not intent.relationship)


st.title("从模糊兴趣开始")
st.caption("AI Intent Studio · 把自然语言兴趣整理成可确认的研究目标与探索路径。")
public_deployment = os.getenv("PUBLIC_DEPLOYMENT", "false").lower() == "true"
public_qwen_ready = public_budget_enabled() if public_deployment else True
if public_deployment:
    if not public_qwen_ready:
        st.info("实时 AI 暂未开放，当前可使用规则搜索或历史演示。")
else:
    try:
        used_calls = int(json.loads(LEDGER.read_text(encoding="utf-8")).get("attempts", 0))
        if used_calls >= MAX_CALLS:
            st.info(f"本轮 Qwen 测试额度已用完（{used_calls}/{MAX_CALLS}）；新输入将明确使用规则降级，不会再发付费请求。")
    except (OSError, ValueError):
        st.warning("无法读取 Qwen 预算账本；付费调用将被预算保护阻止。")
mode_help = ("实时 AI 暂未开放；选择后将使用本地规则，不会发送付费请求。"
             if public_deployment and not public_qwen_ready else
             "公网实时 AI 受服务端预算保护。" if public_deployment else
             "Qwen 调用受现有开发预算账本限制；失败后会明确标记规则降级。")
with st.form("interest_form"):
    interest = st.text_area("你的研究兴趣", value=st.session_state.get("interest", ""),
                            placeholder="例如：想比较神经网络和高斯过程在控制理论中的研究思路……")
    mode = st.radio("规划方式", ["Qwen AI", "本地规则 V1"],
                    index=1 if public_deployment and not public_qwen_ready else 0,
                    horizontal=True, help=mode_help)
    submitted = st.form_submit_button("理解研究意图", type="primary")

snapshot_clicked = st.button("载入已验证 Golden Case（历史 Snapshot · 不调用 API）", help=
    "使用此前保存的真实 Qwen 规划与 OpenAlex 结果，只用于复现原型，不会发起网络请求。")

if snapshot_clicked:
    intent, branches, metadata, outcomes = load_golden_snapshot()
    for key in ("selected_path", "selected_outcome", "selected_report", "confirmed_intent", "next_query_draft"):
        st.session_state.pop(key, None)
    st.session_state.interest = intent.original_interest
    st.session_state.draft_intent = intent
    st.session_state.draft_paths = branches
    st.session_state.plan_source = "qwen_snapshot"
    st.session_state.plan_meta = metadata
    st.session_state.path_outcomes = outcomes
    st.session_state.plan_notice = "Historical snapshot: saved Qwen planning and OpenAlex V1 records. No API call was made."
    st.rerun()

if submitted:
    if not interest.strip():
        st.error("请先输入研究兴趣。")
    else:
        for key in ("selected_path", "selected_outcome", "selected_report", "path_outcomes", "confirmed_intent",
                    "paths_confirmed", "clarification_seen", "plan_meta", "next_query_draft"):
            st.session_state.pop(key, None)
        st.session_state.interest = interest.strip()
        st.session_state.plan_notice = ""
        if mode == "Qwen AI" and public_deployment and not public_qwen_ready:
            intent = parse_intent(interest.strip())
            branches = build_planned_branches(intent)[:3]
            st.session_state.plan_source = "rules_fallback"
            st.session_state.plan_notice = "实时 AI 暂未开放；已使用本地规则 V1，没有调用 Qwen。"
        elif mode == "Qwen AI":
            _deployment_secrets()
            try:
                with st.spinner("Qwen 正在理解意图并规划 2–3 条路径……"):
                    intent, branches, metadata = plan_with_qwen(interest.strip())
                st.session_state.plan_source = "qwen_live"
                st.session_state.plan_meta = metadata
            except QwenPlanningError as exc:
                intent = parse_intent(interest.strip())
                branches = build_planned_branches(intent)[:3]
                st.session_state.plan_source = "rules_fallback"
                st.session_state.plan_notice = f"Qwen 未生成有效规划；以下是本地规则结果。原因：{exc}"
        else:
            intent = parse_intent(interest.strip())
            branches = build_planned_branches(intent)[:3]
            st.session_state.plan_source = "rules_v1"
        st.session_state.draft_intent = intent
        st.session_state.draft_paths = branches
        st.rerun()

intent = st.session_state.get("draft_intent")
if intent:
    source = st.session_state.get("plan_source", "rules_v1")
    if source == "qwen_live":
        meta = st.session_state.plan_meta
        st.success(f"真实 Qwen 规划 · {meta['model']} · {meta['input_tokens']} 输入 / "
                   f"{meta['output_tokens']} 输出 Token · ¥{meta['cost_cny']} · {meta['latency_ms'] / 1000:.1f} 秒")
    elif source == "qwen_snapshot":
        meta = st.session_state.plan_meta
        st.info(f"历史 Snapshot · 真实 Qwen 规划（{meta['model']}，{meta['input_tokens']} 输入 / {meta['output_tokens']} 输出 Token）· 未调用 API。OpenAlex 结果亦来自已保存快照。")
    elif source == "rules_fallback":
        st.warning(st.session_state.get("plan_notice", "Qwen 不可用；已使用本地规则。"))
    else:
        st.info(st.session_state.get("plan_notice") or "本地规则 V1 规划；没有调用 Qwen。")

    st.subheader("系统理解的研究目标")
    st.caption("领域、方法关系和研究目标是系统理解，仍需你确认。硬约束只来自你的明确输入。")
    st.write(f"**领域**：{intent.domain or '待确认'}  ·  **来源 → 目标**："
             f"{intent.source_method or '待确认'} → {intent.target_method or '待确认'}")
    st.write(f"**任务**：{intent.task or '待确认'}  ·  **关系**：{intent.relationship or '待确认'}")
    st.write(f"**明确约束**：{'；'.join(intent.explicit_constraints) or '无'}")
    if intent.inferred:
        st.caption("系统推断（不是用户硬约束）：" + "；".join(intent.inferred))
    if intent.unconfirmed:
        st.caption("尚未确认：" + "；".join(intent.unconfirmed))
    with st.expander("查看字段来源"):
        st.json(intent.field_provenance)

    if _needs_one_question(intent) and not st.session_state.get("clarification_seen"):
        st.warning("存在影响检索的关键歧义。可以补充一次，也可以跳过并直接编辑下方字段。")
        with st.form("one_clarification"):
            answer = st.text_input("请补充研究领域；若两种方法都有，说明比较或迁移方向")
            answer_submitted = st.form_submit_button("补充")
            skipped = st.form_submit_button("跳过")
        if answer_submitted or skipped:
            st.session_state.clarification_seen = True
            if answer_submitted and answer.strip():
                for key in ("selected_path", "selected_outcome", "selected_report", "path_outcomes", "confirmed_intent"):
                    st.session_state.pop(key, None)
                st.session_state.draft_intent = replace(intent, domain=intent.domain or answer.strip(),
                    relationship=intent.relationship or (answer.strip() if intent.source_method and intent.target_method else ""))
                st.session_state.draft_paths = build_planned_branches(st.session_state.draft_intent)[:3]
                st.session_state.plan_source = "rules_after_edit"
                st.session_state.plan_notice = "补充信息后由本地规则重新规划；没有再次调用 Qwen。"
            st.rerun()

    with st.form("intent_editor"):
        domain = st.text_input("研究领域", value=intent.domain)
        source_method = st.text_input("来源方法（灵感来源，可空）", value=intent.source_method)
        target_method = st.text_input("目标方法（拟探索，可空）", value=intent.target_method)
        task = st.text_input("研究目标", value=intent.task)
        relationship = st.text_input("比较 / 迁移关系", value=intent.relationship)
        constraints = st.text_input("明确约束（可空）", value=intent.constraints)
        edit = st.form_submit_button("保存修改并更新路径")
        confirm = st.form_submit_button("确认意图，查看研究路径", type="primary")
    if edit or confirm:
        values = (domain.strip(), source_method.strip(), target_method.strip(), task.strip(),
                  relationship.strip(), constraints.strip())
        original = (intent.domain, intent.source_method, intent.target_method, intent.task,
                    intent.relationship, intent.constraints)
        changed = values != original
        if changed:
            for key in ("selected_path", "selected_outcome", "selected_report", "path_outcomes", "confirmed_intent", "next_query_draft"):
                st.session_state.pop(key, None)
            revised = replace(intent, domain=values[0], theme=values[0] or intent.theme,
                source_method=values[1], target_method=values[2], task=values[3], relationship=values[4],
                constraints=values[5], explicit_constraints=(values[5],) if values[5] else (),
                concepts=normalize_concepts(" ".join(values[1:3])),
                field_provenance={**intent.field_provenance, **{key: "用户修改" for key in
                    ("domain", "source_method_role", "target_method_role", "task", "relationship_direction", "constraints")}})
            st.session_state.draft_intent = revised
            st.session_state.draft_paths = build_planned_branches(revised)[:3]
            st.session_state.plan_source = "rules_after_edit"
            st.session_state.plan_notice = "意图已修改；路径由本地规则按新字段重新生成，未再次调用 Qwen。"
        if confirm:
            st.session_state.confirmed_intent = st.session_state.draft_intent
            st.session_state.paths_confirmed = True
            st.switch_page("pages/2_Path_Explorer.py")
        st.rerun()

    st.caption(f"当前候选路径：{len(st.session_state.get('draft_paths', []))} 条。确认后选择路径，才会调用 OpenAlex。")

st.divider()
st.page_link("pages/2_Evaluation.py", label="人工评测 Evaluation", icon="📋")
