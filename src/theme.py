from __future__ import annotations

from pathlib import Path

import streamlit as st

_NAV_ITEMS: list[tuple[str, str]] = [
    ("app.py", "Análise Temporal"),
    ("pages/5_React_POC.py", "React POC"),
]

_THEME_CSS = """
<style>
    :root {
        --bg: #f7f8fa;
        --card: #ffffff;
        --ink: #111827;
        --muted: #6b7280;
        --line: #e5e7eb;
        --accent: #5b7537;
        --accent-soft: #eef2e4;
        --danger: #b00020;
        --radius: 10px;
    }

    .stApp {
        background: var(--bg);
        color: var(--ink);
    }

    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 1.2rem;
    }

    h1, h2, h3 {
        letter-spacing: -0.01em;
    }

    [data-testid="stMetricValue"] {
        color: var(--ink);
    }

    [data-testid="stMetricLabel"] {
        color: var(--muted);
        font-weight: 600;
    }

    [data-testid="stSidebar"] {
        border-right: 1px solid var(--line);
    }

    [data-testid="stSidebarNav"] [data-testid="stSidebarNavLinkLabel"] {
        line-height: 1.2;
    }

    [data-testid="stFileUploader"] section {
        border: 1px dashed var(--accent) !important;
        border-radius: var(--radius) !important;
        background: var(--accent-soft) !important;
    }

    [data-testid="stButton"] button {
        border-radius: var(--radius);
        border: 1px solid var(--line);
    }

    [data-testid="stButton"] button[kind="primary"] {
        background: var(--accent);
        border-color: var(--accent);
        color: #ffffff;
        font-weight: 600;
    }

    [data-testid="stButton"] button[kind="primary"]:hover {
        background: #4f6630;
        border-color: #4f6630;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: var(--radius);
        overflow: hidden;
    }

    .brain-card {
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: 0.75rem 0.95rem;
        background: var(--card);
    }

    .brain-note {
        color: var(--muted);
        font-size: 0.9rem;
    }

</style>
"""


def _resolve_logo_path() -> str | None:
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / "assets" / "logoBrain.png",
        root / "assets" / "logo.png",
        root / "assets" / "logo_empresa.png",
    ]
    for logo in candidates:
        if logo.exists():
            return str(logo)
    return None


def apply_brain_theme() -> None:
    """Apply shared CSS tokens and component styling."""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def render_sidebar_menu() -> None:
    """Render sidebar branding and manual navigation links."""
    logo_path = _resolve_logo_path()
    with st.sidebar:
        if logo_path:
            try:
                st.logo(logo_path, size="large")
            except Exception:
                st.image(logo_path, width=112)

        sidebar_page_link = getattr(st.sidebar, "page_link", None)
        if callable(sidebar_page_link):
            for page_path, label in _NAV_ITEMS:
                st.page_link(page_path, label=label)
        else:
            for page_path, label in _NAV_ITEMS:
                if st.button(label, width="stretch", key=f"nav_{page_path}"):
                    st.switch_page(page_path)
