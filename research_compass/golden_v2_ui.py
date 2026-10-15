"""Small, opt-in Page 3 view for the human-curated Golden Case v2."""

import streamlit as st


def render_golden_v2_cards(cards: list[dict]) -> None:
    st.subheader("Research Opportunity Cards · 人工策划示例")
    st.info("Human-curated Golden Case v2 Snapshot · 2026-10-14 的 OpenAlex 摘要及人工裁定。"
            "以下研究问题由人工整理，迁移假设均待验证；不是实时 Qwen 输出，也不是新检索结果。")
    columns = st.columns(3)
    for card, column in zip(cards, columns):
        with column, st.container(border=True):
            st.markdown(f"### {card['key']} · {card['title']}")
            st.caption("证据覆盖：" + card["evidence_maturity"])
            st.markdown("**Research Question**")
            st.write(card["research_question"])
            with st.expander("Evidence-backed Background · 查看摘要依据"):
                for item in card["evidence_backed_background"]:
                    st.write(f"**{item['role']} · {item['paper_title']}**")
                    st.write(item["claim"])
                    st.markdown(f"> {item['quote']}")
                    st.link_button(f"OpenAlex · {item['paper_id'].rsplit('/', 1)[-1]}", item["openalex_url"])
                    st.caption("原始 Evidence Gate：Evidence Eligible；人工准入：yes；仅据摘要。")
            st.markdown("**Transfer Hypothesis · 待验证**")
            st.warning(card["transfer_hypothesis"])
            st.markdown("**Evidence Gaps**")
            for gap in card["evidence_gaps"]:
                st.write("• " + gap)
            if card["further_reading"]:
                with st.expander("Further Reading · 未获证据准入"):
                    for item in card["further_reading"]:
                        st.link_button(item["paper_title"], item["openalex_url"])
                        st.caption(f"原相关性 {item['human_relevance_label']} / 人工准入 "
                                   f"{item['human_evidence_eligible_label']} · {item['reason']}")
            st.markdown("**Next Action**")
            st.write(card["next_action"])
            query = st.text_input("Editable English Search Query", value=card["english_search_query"],
                                  key=f"golden_v2_query_{card['key']}")
            st.code(query, language=None)
            if st.button("带此查询进入真实检索", key=f"golden_v2_search_{card['key']}"):
                if not query.strip() or not query.isascii() or len(query) > 360:
                    st.error("请使用不超过 360 字符的英文检索式。")
                else:
                    st.session_state.next_query_draft = query.strip()
                    st.session_state.golden_v2_next_card = card["key"]
                    st.switch_page("pages/2_Path_Explorer.py")
