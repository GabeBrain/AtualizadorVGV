from __future__ import annotations

import streamlit as st

from src.theme import apply_brain_theme, render_sidebar_menu

APP_NAME = "Comparador de Índices"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon=":balance_scale:")
apply_brain_theme()
render_sidebar_menu()

st.title(APP_NAME)
st.caption("Página reservada para a próxima etapa do projeto.")
st.info("Em construção.")
