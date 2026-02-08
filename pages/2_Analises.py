from __future__ import annotations

import altair as alt
import streamlit as st

from src.analytics import apply_date_filter, daily_aggregation, kpi_snapshot, top_categories
from src.theme import apply_brain_theme, render_sidebar_menu

st.set_page_config(page_title="Analises", layout="wide")
apply_brain_theme()
render_sidebar_menu()

st.title("Analises")
st.caption("KPIs e visualizacoes para leitura rapida do dataset.")

analysis_df = st.session_state.get("analysis_df")
if analysis_df is None or analysis_df.empty:
    st.warning("Nenhum dataset de analise disponivel. Va para `Upload` e salve o mapeamento.")
    st.stop()

work_df = analysis_df.copy()

if "date" in work_df.columns and work_df["date"].notna().any():
    min_date = work_df["date"].dropna().min().date()
    max_date = work_df["date"].dropna().max().date()
    start_date, end_date = st.date_input("Periodo", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    work_df = apply_date_filter(work_df, start_date, end_date)

snapshot = kpi_snapshot(work_df)

metric_cols = st.columns(4)
metric_cols[0].metric("Linhas", f"{int(snapshot['rows']):,}".replace(",", "."))
metric_cols[1].metric("Linhas mapeadas", f"{int(snapshot['mapped_rows']):,}".replace(",", "."))
metric_cols[2].metric("Soma (valor)", f"{snapshot['value_sum']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
metric_cols[3].metric("Taxa de nulos", f"{snapshot['null_rate'] * 100:.1f}%")

if "value" in work_df.columns and work_df["value"].notna().any():
    st.subheader("Distribuicao de valor")
    hist = (
        alt.Chart(work_df.dropna(subset=["value"]))
        .mark_bar(color="#5b7537")
        .encode(
            alt.X("value:Q", bin=alt.Bin(maxbins=35), title="Valor"),
            alt.Y("count()", title="Frequencia"),
            tooltip=["count()"],
        )
        .properties(height=280)
    )
    st.altair_chart(hist, use_container_width=True)

if "date" in work_df.columns and "value" in work_df.columns:
    daily = daily_aggregation(work_df)
    if not daily.empty:
        st.subheader("Serie diaria (soma de valor)")
        line = (
            alt.Chart(daily)
            .mark_line(point=True, color="#1f4e7a")
            .encode(
                x=alt.X("day:T", title="Dia"),
                y=alt.Y("value_sum:Q", title="Soma de valor"),
                tooltip=["day:T", "value_sum:Q"],
            )
            .properties(height=280)
        )
        st.altair_chart(line, use_container_width=True)

category_col = None
if "category" in work_df.columns:
    category_col = "category"
elif "status" in work_df.columns:
    category_col = "status"

if category_col is not None:
    st.subheader(f"Top {category_col}")
    top_df = top_categories(work_df, category_col, limit=10)
    bars = (
        alt.Chart(top_df)
        .mark_bar(color="#2e4a19")
        .encode(
            x=alt.X("count:Q", title="Volume"),
            y=alt.Y(f"{category_col}:N", sort="-x", title=category_col),
            tooltip=[category_col, "count"],
        )
        .properties(height=320)
    )
    st.altair_chart(bars, use_container_width=True)

with st.expander("Preview dos dados mapeados", expanded=False):
    st.dataframe(work_df.head(200), use_container_width=True, hide_index=True)
