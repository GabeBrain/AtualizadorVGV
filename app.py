from __future__ import annotations

import streamlit as st

from src.theme import apply_brain_theme, render_sidebar_menu

APP_NAME = "Atualizador de VGV"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon=":bar_chart:")
apply_brain_theme()
render_sidebar_menu()

st.title(APP_NAME)
st.caption("Starter padrao Brain para apps Streamlit com upload de Excel e analises rapidas.")

st.markdown(
    """
    <div class="brain-card">
        <strong>Fluxo recomendado</strong><br/>
        1) Upload do Excel e mapeamento das colunas<br/>
        2) Analises de negocio com filtros e graficos<br/>
        3) Qualidade e exportacao de dados
    </div>
    """,
    unsafe_allow_html=True,
)

raw_df = st.session_state.get("raw_df")
analysis_df = st.session_state.get("analysis_df")

left, right = st.columns(2)
with left:
    st.subheader("Estado atual")
    if raw_df is None:
        st.info("Nenhum arquivo carregado ainda.")
    else:
        st.success("Arquivo carregado.")
        st.write(f"- Linhas brutas: `{len(raw_df):,}`".replace(",", "."))
        st.write(f"- Colunas brutas: `{raw_df.shape[1]}`")
        source_file_name = st.session_state.get("source_file_name")
        if source_file_name:
            st.write(f"- Arquivo: `{source_file_name}`")

with right:
    st.subheader("Pronto para analise")
    if analysis_df is None:
        st.warning("Mapeie as colunas na pagina `Upload` para liberar analises.")
    else:
        st.success("Dataset de analise preparado.")
        st.write(f"- Linhas mapeadas: `{len(analysis_df):,}`".replace(",", "."))
        st.write(f"- Campos mapeados: `{analysis_df.shape[1]}`")

st.markdown(
    """
    <div class="brain-note">
        Dica: para manter padrao entre apps da empresa, centralize ajustes visuais em
        <code>src/theme.py</code>.
    </div>
    """,
    unsafe_allow_html=True,
)
