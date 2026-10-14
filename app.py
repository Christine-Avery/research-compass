"""Research Compass explicit Streamlit page registry."""

import os

import streamlit as st


def _load_private_settings() -> None:
    """Read deployment secrets into process env without displaying them."""
    names = (
        "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "DASHSCOPE_MODEL", "OPENALEX_API_KEY",
        "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "PUBLIC_BUDGET_HMAC_KEY",
        "PUBLIC_DEPLOYMENT", "PUBLIC_QWEN_ENABLED", "PUBLIC_QWEN_SECURITY_REVIEW_PASSED",
    )
    for name in names:
        if os.getenv(name):
            continue
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None
        if value is not None:
            os.environ[name] = str(value).lower() if isinstance(value, bool) else str(value)


_load_private_settings()

home_page = st.Page(
    "pages/1_Intent_Studio.py",
    title="AI Intent Studio",
    default=True,
)
paths_page = st.Page(
    "pages/2_Path_Explorer.py",
    title="Research Path Explorer",
    url_path="paths",
)
evidence_page = st.Page(
    "pages/3_Evidence_Next.py",
    title="Evidence & Next Steps",
    url_path="evidence",
)
classic_page = st.Page(
    "pages/1_Home.py",
    title="V1 Classic Baseline",
    url_path="classic",
)
evaluation_page = st.Page(
    "pages/2_Evaluation.py",
    title="人工评测 Evaluation",
    url_path="evaluation",
)

# Main-content page links are available on both routes, so the app does not
# depend on the sidebar being visible.
navigation = st.navigation([home_page, paths_page, evidence_page, evaluation_page, classic_page], position="hidden")
navigation.run()
