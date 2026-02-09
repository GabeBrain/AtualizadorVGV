from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from src.analytics import null_report
from src.theme import apply_brain_theme, render_sidebar_menu

st.set_page_config(page_title="Qualidade", layout="wide")
apply_brain_theme()
render_sidebar_menu()

st.title("Qualidade e exportacao")
st.caption("Checklist basico de qualidade e download do dataset tratado.")

analysis_df = st.session_state.get("analysis_df")
if analysis_df is None or analysis_df.empty:
    st.warning("Nenhum dataset de analise disponivel. Va para `Upload` e salve o mapeamento.")
    st.stop()

work_df = analysis_df.copy()

st.subheader("Qualidade por coluna")
st.dataframe(null_report(work_df), width="stretch", hide_index=True)

dup_count = 0
if "id" in work_df.columns:
    dup_count = int(work_df["id"].duplicated(keep=False).sum())

negative_count = 0
if "value" in work_df.columns:
    negative_count = int((work_df["value"].fillna(0) < 0).sum())

future_count = 0
if "date" in work_df.columns:
    today = pd.Timestamp.now().normalize()
    future_count = int((work_df["date"].dropna() > today).sum())

check_cols = st.columns(3)
check_cols[0].metric("IDs duplicados", dup_count)
check_cols[1].metric("Valores negativos", negative_count)
check_cols[2].metric("Datas futuras", future_count)

st.subheader("Acoes de limpeza")
remove_duplicates = st.checkbox("Remover duplicados por ID (manter primeira ocorrencia)", value=True)
drop_negative_values = st.checkbox("Remover linhas com valor negativo", value=False)
drop_future_dates = st.checkbox("Remover linhas com data futura", value=False)

clean_df = work_df.copy()
if remove_duplicates and "id" in clean_df.columns:
    clean_df = clean_df.drop_duplicates(subset=["id"], keep="first")
if drop_negative_values and "value" in clean_df.columns:
    clean_df = clean_df[(clean_df["value"].isna()) | (clean_df["value"] >= 0)]
if drop_future_dates and "date" in clean_df.columns:
    today = pd.Timestamp.now().normalize()
    clean_df = clean_df[(clean_df["date"].isna()) | (clean_df["date"] <= today)]

st.write(f"Linhas apos limpeza: `{len(clean_df):,}`".replace(",", "."))
st.dataframe(clean_df.head(200), width="stretch", hide_index=True)

csv_data = clean_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Baixar CSV tratado",
    data=csv_data,
    file_name="dataset_tratado.csv",
    mime="text/csv",
    type="primary",
)

excel_buffer = BytesIO()
with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
    clean_df.to_excel(writer, index=False, sheet_name="dados_tratados")

st.download_button(
    "Baixar XLSX tratado",
    data=excel_buffer.getvalue(),
    file_name="dataset_tratado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
