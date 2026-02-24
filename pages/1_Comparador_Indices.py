from __future__ import annotations

import pandas as pd
import streamlit as st

from src.theme import apply_brain_theme, render_sidebar_menu

APP_NAME = "Comparador de Índices"
SHARED_SOURCE_TOKEN_KEY = "__shared_source_token"
SHARED_SOURCE_NAME_KEY = "__shared_source_name"
SHARED_BASE_DF_KEY = "__shared_base_df"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon=":balance_scale:")
apply_brain_theme()
render_sidebar_menu()

st.title(APP_NAME)
st.caption("Esta pagina consome o mesmo arquivo carregado no Atualizador de VGV.")

shared_token = st.session_state.get(SHARED_SOURCE_TOKEN_KEY)
shared_source_name = st.session_state.get(SHARED_SOURCE_NAME_KEY) or "-"
shared_base_df = st.session_state.get(SHARED_BASE_DF_KEY)

if shared_token is None or shared_base_df is None:
    st.warning("Nenhum arquivo ativo. Carregue a planilha na pagina Atualizador de VGV.")
    st.stop()

if not isinstance(shared_base_df, pd.DataFrame):
    st.error("O dataset compartilhado esta invalido. Recarregue a planilha na pagina principal.")
    st.stop()

st.success(f"Fonte compartilhada ativa: {shared_source_name}")
st.subheader("Preview do dataframe resultante (head 5)")
st.dataframe(shared_base_df.head(5), width="stretch", hide_index=True)
