from __future__ import annotations

import streamlit as st

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

    html, body, [class*="css"] {
        font-size: 13.5px !important;
        font-family: "Tahoma", sans-serif !important;
        background: var(--bg);
        color: var(--ink);
    }

    .stApp {
        background: var(--bg);
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

    [data-testid="stSidebar"] * {
        font-family: "Tahoma", sans-serif !important;
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


def apply_brain_theme() -> None:
    """Apply shared CSS tokens and component styling."""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)
