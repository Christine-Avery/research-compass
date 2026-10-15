"""Single-path opportunity view for the reviewed Golden Case demonstration."""

import streamlit as st


def render_golden_v2_card(mapping: dict, card: dict, path_title: str) -> None:
    """Show only the card explicitly mapped to the selected historical path."""
    st.caption("当前探索路径")
    st.subheader(path_title)
    st.markdown(f"### 研究方向 · {card['title']}")
    st.write(mapping["progression"])

    with st.container(border=True):
        st.caption("证据覆盖：" + card["evidence_maturity"])
        st.markdown("**Research Question · 待验证**")
        st.write(card["research_question"])
        st.markdown("**Evidence-backed Background · 已准入摘要依据**")
        st.caption("以下文献来自完整 Golden Case 历史检索；跨路径引用会单独标记。仅核查摘要，未核验全文。")
        for item in card["evidence_backed_background"]:
            origin = ("当前路径历史检索" if item["retrieval_branch"] == mapping["retrieval_branch"]
                      else "跨路径补充文献")
            with st.expander(f"{origin} · {item['paper_title']}"):
                st.write(item["claim"])
                st.markdown(f"> {item['quote']}")
                st.link_button(f"OpenAlex · {item['paper_id'].rsplit('/', 1)[-1]}", item["openalex_url"])
                st.caption("已通过原证据准入与人工复核；仅支持上方对应摘要陈述。")

        st.markdown("**Transfer Hypothesis · 待验证**")
        st.warning(card["transfer_hypothesis"])
        st.markdown("**Evidence Gaps**")
        for gap in card["evidence_gaps"]:
            st.write("• " + gap)
        if card["further_reading"]:
            with st.expander("Further Reading · 未获证据准入"):
                for item in card["further_reading"]:
                    origin = ("当前路径历史检索" if item["retrieval_branch"] == mapping["retrieval_branch"]
                              else "跨路径补充文献")
                    st.link_button(item["paper_title"], item["openalex_url"])
                    st.caption(f"{origin} · 尚未获准用于生成研究结论，仅作阅读线索。")
        st.markdown("**Next Action**")
        st.write(card["next_action"])

    st.subheader("Next Search · 继续检索")
    query = st.text_input("英文检索式（可修改）", value=card["english_search_query"],
                          key=f"golden_v2_query_{mapping['path_id']}")
    st.code(query, language=None)
    if st.button("继续检索", type="primary"):
        if not query.strip() or not query.isascii() or len(query) > 360:
            st.error("请使用不超过 360 字符的英文检索式。")
        else:
            st.session_state.next_query_draft = query.strip()
            st.session_state.golden_v2_next_card = card["key"]
            st.switch_page("pages/2_Path_Explorer.py")

    st.subheader("Research Plan Summary")
    summary = "\n".join([
        "# 下一步研究计划",
        f"- 当前探索路径：{path_title}",
        f"- 研究方向：{card['title']}",
        f"- 方向递进：{mapping['progression']}",
        f"- 待验证研究问题：{card['research_question']}",
        "- 已准入的摘要依据：" + "、".join(item["paper_id"] for item in card["evidence_backed_background"]),
        "- 证据缺口：" + "；".join(card["evidence_gaps"]),
        f"- 下一步行动：{card['next_action']}",
        f"- 下一轮英文检索式：{query}",
    ])
    st.code(summary, language="markdown")
    st.download_button("下载 Research Plan Summary", summary, file_name="research-plan-summary.md", mime="text/markdown")
    st.page_link("pages/2_Path_Explorer.py", label="返回研究路径，探索其他方向 →", icon="🧭")
    st.caption("本演示使用已保存的真实文献数据；候选研究问题仍需验证。")
