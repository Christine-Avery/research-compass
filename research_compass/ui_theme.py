"""Small, shared visual layer for the three core Streamlit pages."""

import streamlit as st


COLORS = {
    "navy": "#142B43",
    "teal": "#287D8E",
    "soft_blue": "#EAF3F5",
    "canvas": "#F8FAFC",
}


def apply_theme() -> None:
    """Apply restrained CSS using document-level selectors only."""
    st.markdown(
        """
        <style>
          body { background: #F8FAFC; }
          main .block-container { max-width: 1200px; padding: 1.35rem 1.5rem 3rem; }
          h1, h2, h3 { color: #142B43; letter-spacing: -0.02em; }
          p, li, label, [data-testid="stMarkdownContainer"] { color: #24394B; }
          a { color: #287D8E; }
          button[kind="primary"] { background: #287D8E; border-color: #287D8E; }
          input, textarea { border-radius: 0.65rem !important; }
          blockquote { background: #EAF3F5; border-left-color: #287D8E; padding: .75rem 1rem; }
          code { border-radius: .45rem; }
          pre, pre code { white-space: pre-wrap !important; overflow-wrap: anywhere !important; word-break: break-word; }
          @media (max-width: 800px) {
            main .block-container { padding: 1rem 1rem 2.5rem; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(active_step: int) -> None:
    """Consistent product header and visible three-step navigation."""
    apply_theme()
    brand, step1, step2, step3 = st.columns([2.2, 1.1, 1.2, 1.25], vertical_alignment="center")
    with brand:
        st.markdown("**🧭 Research Compass**")
        st.caption("Academic Research Workspace")
    steps = [
        (step1, 1, "AI Intent Studio", "pages/1_Intent_Studio.py"),
        (step2, 2, "Research Paths", "pages/2_Path_Explorer.py"),
        (step3, 3, "Evidence & Next", "pages/3_Evidence_Next.py"),
    ]
    for column, number, label, target in steps:
        with column:
            prefix = "●" if number == active_step else str(number)
            st.page_link(target, label=f"{prefix}  {label}")
    st.divider()
