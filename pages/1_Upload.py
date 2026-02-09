from __future__ import annotations

import streamlit as st

from src.io_excel import (
    NONE_OPTION,
    build_column_profile,
    prepare_analysis_dataframe,
    read_excel_file,
    suggest_default_map,
)
from src.theme import apply_brain_theme, render_sidebar_menu

st.set_page_config(page_title="Upload", layout="wide")
apply_brain_theme()
render_sidebar_menu()

st.title("Upload e mapeamento")
st.caption("Suba o Excel e defina quais colunas serao usadas nas analises.")

uploaded_file = st.file_uploader(
    "Arquivo Excel (.xlsx, .xls)",
    type=["xlsx", "xls"],
    help="A primeira aba do arquivo sera utilizada.",
)

if uploaded_file is not None:
    try:
        raw_df = read_excel_file(uploaded_file, normalize_columns=True)
    except Exception as exc:
        st.error(f"Nao foi possivel ler o Excel: {exc}")
        st.stop()

    st.session_state["raw_df"] = raw_df
    st.session_state["source_file_name"] = uploaded_file.name

raw_df = st.session_state.get("raw_df")
if raw_df is None:
    st.info("Carregue um Excel para continuar.")
    st.stop()

profile = build_column_profile(raw_df)
defaults = st.session_state.get("column_map") or suggest_default_map(profile)
options = [NONE_OPTION] + profile.all_columns


def _option_index(value: str) -> int:
    if value in options:
        return options.index(value)
    return 0


st.subheader("Mapeamento padrao")
with st.form("column_map_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        map_id = st.selectbox("Coluna de ID", options, index=_option_index(defaults.get("id", NONE_OPTION)))
        map_date = st.selectbox("Coluna de Data", options, index=_option_index(defaults.get("date", NONE_OPTION)))
        map_value = st.selectbox(
            "Coluna de Valor numerico",
            options,
            index=_option_index(defaults.get("value", NONE_OPTION)),
        )
    with col2:
        map_category = st.selectbox(
            "Coluna de Categoria",
            options,
            index=_option_index(defaults.get("category", NONE_OPTION)),
        )
        map_status = st.selectbox(
            "Coluna de Status",
            options,
            index=_option_index(defaults.get("status", NONE_OPTION)),
        )

    save_mapping = st.form_submit_button("Salvar mapeamento", type="primary")

if save_mapping:
    column_map = {
        "id": map_id,
        "date": map_date,
        "value": map_value,
        "category": map_category,
        "status": map_status,
    }
    analysis_df = prepare_analysis_dataframe(raw_df, column_map)
    st.session_state["column_map"] = column_map
    st.session_state["analysis_df"] = analysis_df
    st.success("Mapeamento salvo. As paginas de analise e qualidade foram liberadas.")

st.subheader("Resumo do arquivo")
summary1, summary2, summary3, summary4 = st.columns(4)
summary1.metric("Linhas", f"{len(raw_df):,}".replace(",", "."))
summary2.metric("Colunas", raw_df.shape[1])
summary3.metric("Numericas", len(profile.numeric_columns))
summary4.metric("Datas", len(profile.datetime_columns))

with st.expander("Ver colunas detectadas", expanded=False):
    st.write("Todas:", profile.all_columns)
    st.write("Numericas:", profile.numeric_columns)
    st.write("Datas:", profile.datetime_columns)
    st.write("Categoriais:", profile.categorical_columns)

st.subheader("Preview")
st.dataframe(raw_df.head(200), width="stretch", hide_index=True)
