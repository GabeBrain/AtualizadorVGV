from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from src.react_component import render_react_workspace
from src.theme import apply_brain_theme, render_sidebar_menu
from src.vgv_core import (
    build_reajuste_dataset as core_build_reajuste_dataset,
    clean_options as core_clean_options,
    find_column as core_find_column,
    format_brl_compact as core_format_brl_compact,
    source_token as core_source_token,
    to_excel_bytes as core_to_excel_bytes,
)
from src.vgv_parser import parse_vgv_workbook

APP_NAME = "Atualizador de VGV - React POC"
REAJUSTE_BASE_DATE = pd.Timestamp("2025-12-01")

CITY_FILTER_KEY = "react_filter_cidades"
TIPO_FILTER_KEY = "react_filter_tipologias"
STATUS_FILTER_KEY = "react_filter_status"
FOCUS_EMP_KEY = "react_focus_empreendimento"
REACT_SOURCE_TOKEN_KEY = "__react_loaded_source_token"

st.set_page_config(page_title="React POC", layout="wide", page_icon=":rocket:")
apply_brain_theme()
render_sidebar_menu()


@st.cache_data(show_spinner=False)
def _parse_uploaded(file_bytes: bytes):
    return parse_vgv_workbook(BytesIO(file_bytes))


@st.cache_data(show_spinner=False)
def _parse_sample(path_text: str):
    return parse_vgv_workbook(path_text)


@st.cache_data(show_spinner=False)
def _build_reajuste_dataset(
    perf_source: pd.DataFrame,
    incc_path_text: str,
    target_months: tuple[str, ...] | None,
    base_date_text: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    return core_build_reajuste_dataset(
        perf_source=perf_source,
        incc_path_text=incc_path_text,
        target_months=target_months,
        base_date_text=base_date_text,
        fallback_base_date=REAJUSTE_BASE_DATE,
    )


def _spinner_with_timer(message: str):
    try:
        return st.spinner(message, show_time=True)
    except TypeError:
        return st.spinner(message)


st.title(APP_NAME)
st.caption(
    "POC paralela da experiencia React. A pagina nativa continua como baseline para comparacao direta."
)

sample_path = Path(__file__).resolve().parents[1] / "assets" / "tabelaEmpreendimentoReduzida.xlsx"

with st.expander("Fonte de dados", expanded=True):
    uploaded_file = st.file_uploader("Planilha no formato padrao", type=["xlsx", "xls"], key="react_source_uploader")
    b1, b2, _ = st.columns([1, 1, 2])
    use_sample = b1.button("Usar exemplo de assets", width="stretch", disabled=not sample_path.exists())
    clear_source = b2.button("Limpar", width="stretch")

    if uploaded_file is not None:
        st.session_state["source_mode"] = "upload"
        st.session_state["source_name"] = uploaded_file.name
        st.session_state["source_bytes"] = uploaded_file.getvalue()

    if use_sample and sample_path.exists():
        st.session_state["source_mode"] = "sample"
        st.session_state["source_name"] = sample_path.name
        st.session_state.pop("source_bytes", None)

    if clear_source:
        for key in (
            "source_mode",
            "source_name",
            "source_bytes",
            REACT_SOURCE_TOKEN_KEY,
            CITY_FILTER_KEY,
            TIPO_FILTER_KEY,
            STATUS_FILTER_KEY,
            FOCUS_EMP_KEY,
        ):
            st.session_state.pop(key, None)

if "source_mode" not in st.session_state and sample_path.exists():
    st.session_state["source_mode"] = "sample"
    st.session_state["source_name"] = sample_path.name

source_mode = st.session_state.get("source_mode")
source_token_value = core_source_token(
    source_mode,
    st.session_state.get("source_name"),
    st.session_state.get("source_bytes"),
    sample_path,
)
is_new_source = source_token_value is not None and st.session_state.get(REACT_SOURCE_TOKEN_KEY) != source_token_value

base_df: pd.DataFrame | None = None
perf_df: pd.DataFrame | None = None
metadata: dict[str, Any] | None = None

try:
    if source_mode == "upload" and st.session_state.get("source_bytes"):
        if is_new_source:
            with _spinner_with_timer("Carregando planilha enviada..."):
                base_df, perf_df, metadata = _parse_uploaded(st.session_state["source_bytes"])
        else:
            base_df, perf_df, metadata = _parse_uploaded(st.session_state["source_bytes"])
    elif source_mode == "sample" and sample_path.exists():
        if is_new_source:
            with _spinner_with_timer("Carregando planilha de exemplo..."):
                base_df, perf_df, metadata = _parse_sample(str(sample_path))
        else:
            base_df, perf_df, metadata = _parse_sample(str(sample_path))
except Exception as exc:
    st.error(f"Falha ao ler planilha: {exc}")
    st.stop()

if base_df is None or perf_df is None or metadata is None:
    st.info("Carregue uma planilha para iniciar a analise React.")
    st.stop()

if source_token_value is not None:
    st.session_state[REACT_SOURCE_TOKEN_KEY] = source_token_value

if base_df.empty:
    st.warning("A planilha nao possui linhas validas apos a limpeza inicial.")
    st.stop()

month_labels = metadata.get("month_labels", [])

empreendimento_col = core_find_column(list(base_df.columns), ["Empreendimento"])
cidade_col = core_find_column(list(base_df.columns), ["Cidade"])
tipologia_col = core_find_column(list(base_df.columns), ["Tipologia"])
status_metric_col = core_find_column(list(perf_df.columns), ["Status"])
vgv_oferta_col = core_find_column(list(perf_df.columns), ["VGV Oferta Final"])

if not empreendimento_col:
    st.error("A coluna 'Empreendimento' e obrigatoria para a POC React.")
    st.stop()

latest_record = pd.DataFrame(columns=["__registro_id"])
if not perf_df.empty and "MesData" in perf_df.columns:
    latest_record = (
        perf_df.dropna(subset=["MesData"]).sort_values("MesData").groupby("__registro_id", as_index=False).tail(1)
    )

base_enriched = base_df.copy()
if not latest_record.empty and status_metric_col and status_metric_col in latest_record.columns:
    status_frame = latest_record[["__registro_id", status_metric_col]].rename(columns={status_metric_col: "Status Atual"})
    base_enriched = base_enriched.merge(status_frame, on="__registro_id", how="left")

for key in (CITY_FILTER_KEY, TIPO_FILTER_KEY, STATUS_FILTER_KEY):
    st.session_state.setdefault(key, [])
st.session_state.setdefault(FOCUS_EMP_KEY, "")

st.subheader("Filtros base (nativos)")
fc1, fc2, fc3 = st.columns(3)

city_options = core_clean_options(base_enriched[cidade_col]) if cidade_col else []
tipo_options = core_clean_options(base_enriched[tipologia_col]) if tipologia_col else []
status_options = core_clean_options(base_enriched["Status Atual"]) if "Status Atual" in base_enriched.columns else []

st.session_state[CITY_FILTER_KEY] = [v for v in st.session_state[CITY_FILTER_KEY] if v in city_options]
st.session_state[TIPO_FILTER_KEY] = [v for v in st.session_state[TIPO_FILTER_KEY] if v in tipo_options]
st.session_state[STATUS_FILTER_KEY] = [v for v in st.session_state[STATUS_FILTER_KEY] if v in status_options]

fc1.multiselect("Cidade", options=city_options, key=CITY_FILTER_KEY)
fc2.multiselect("Tipologia", options=tipo_options, key=TIPO_FILTER_KEY)
fc3.multiselect("Status atual", options=status_options, key=STATUS_FILTER_KEY)

scope_df = base_enriched.copy()
if cidade_col and st.session_state[CITY_FILTER_KEY]:
    scope_df = scope_df[scope_df[cidade_col].astype(str).isin(st.session_state[CITY_FILTER_KEY])]
if tipologia_col and st.session_state[TIPO_FILTER_KEY]:
    scope_df = scope_df[scope_df[tipologia_col].astype(str).isin(st.session_state[TIPO_FILTER_KEY])]
if "Status Atual" in scope_df.columns and st.session_state[STATUS_FILTER_KEY]:
    scope_df = scope_df[scope_df["Status Atual"].astype(str).isin(st.session_state[STATUS_FILTER_KEY])]

focus_options = core_clean_options(scope_df[empreendimento_col])
current_focus = str(st.session_state.get(FOCUS_EMP_KEY) or "")
if current_focus and current_focus not in focus_options:
    st.session_state[FOCUS_EMP_KEY] = ""
    current_focus = ""

payload = {
    "sourceToken": source_token_value,
    "selectedEmpreendimento": current_focus,
    "empreendimentos": focus_options,
    "summary": {
        "rows": int(len(scope_df)),
        "months": int(len(month_labels)),
        "empreendimentos": int(len(focus_options)),
    },
}

st.subheader("React workspace")
component_event = render_react_workspace(payload=payload, key="react_workspace_main")
new_focus = str(component_event.get("selectedEmpreendimento", "") or "").strip()
if new_focus != current_focus and (not new_focus or new_focus in focus_options):
    st.session_state[FOCUS_EMP_KEY] = new_focus
    st.rerun()

filtered_base = scope_df.copy()
if current_focus:
    filtered_base = filtered_base[filtered_base[empreendimento_col].astype(str) == current_focus]

if filtered_base.empty:
    st.warning("Nenhum registro encontrado com os filtros atuais.")
    st.stop()

filtered_ids = set(filtered_base["__registro_id"].tolist())
filtered_perf = perf_df[perf_df["__registro_id"].isin(filtered_ids)].copy()

reajuste_df = pd.DataFrame()
reajuste_meta: dict[str, Any] = {}
reajuste_error: str | None = None
incc_series_path = Path(__file__).resolve().parents[1] / "assets" / "INCC_Series_MeDI.xlsx"
if incc_series_path.exists():
    try:
        reajuste_df, reajuste_meta = _build_reajuste_dataset(
            perf_source=perf_df,
            incc_path_text=str(incc_series_path),
            target_months=tuple(month_labels) if month_labels else None,
            base_date_text=REAJUSTE_BASE_DATE.strftime("%Y-%m-%d"),
        )
    except Exception as exc:
        reajuste_error = f"Falha ao preparar reajuste INCC: {exc}"
else:
    reajuste_error = "Arquivo INCC_Series_MeDI.xlsx nao encontrado em assets/."

filtered_reajuste = reajuste_df[reajuste_df["__registro_id"].isin(filtered_ids)].copy() if not reajuste_df.empty else pd.DataFrame()

st.subheader("Resumo da POC")
r1, r2, r3, r4 = st.columns(4)
r1.metric("Empreendimentos", len(core_clean_options(filtered_base[empreendimento_col])))
r2.metric("Registros", f"{len(filtered_base):,}".replace(",", "."))
r3.metric("Meses", len(month_labels))
if vgv_oferta_col and not filtered_perf.empty and vgv_oferta_col in filtered_perf.columns:
    value = pd.to_numeric(filtered_perf[vgv_oferta_col], errors="coerce").sum()
    r4.metric("VGV oferta (filtro)", core_format_brl_compact(value))
else:
    r4.metric("VGV oferta (filtro)", "-")

if vgv_oferta_col and "MesData" in filtered_perf.columns and not filtered_perf.empty:
    monthly_plot = (
        filtered_perf.assign(__value=pd.to_numeric(filtered_perf[vgv_oferta_col], errors="coerce"))
        .dropna(subset=["MesData", "__value"])
        .groupby(["Mes", "MesData"], as_index=False)["__value"]
        .sum()
        .sort_values("MesData")
    )
    if not monthly_plot.empty:
        chart = (
            alt.Chart(monthly_plot)
            .mark_line(point=True, color="#2e5f4f")
            .encode(
                x=alt.X("MesData:T", title="Mes"),
                y=alt.Y("__value:Q", title="VGV Oferta Final"),
                tooltip=["Mes", alt.Tooltip("__value:Q", format=",.2f")],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, width="stretch")

with st.expander("Debug de contrato (React <-> Streamlit)", expanded=False):
    st.write("payload enviado para o componente")
    st.json(payload)
    st.write("evento retornado pelo componente")
    st.json(component_event)
    if reajuste_error:
        st.info(reajuste_error)
    else:
        base_date = reajuste_meta.get("base_di_date")
        st.caption(
            "Base INCC usada na POC: "
            + (base_date.strftime("%m/%Y") if isinstance(base_date, pd.Timestamp) else "-")
        )

st.subheader("Exportacao (recorte POC)")
export_sheets = {
    "Empreendimentos": filtered_base,
    "Performance_Mensal": filtered_perf,
    "Reajuste_INCC": filtered_reajuste,
}
export_bytes = core_to_excel_bytes(export_sheets)
st.download_button(
    "Exportar Excel do recorte POC",
    data=export_bytes,
    file_name="dados_vgv_react_poc.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)

with st.expander("Preview de dados filtrados", expanded=False):
    st.dataframe(filtered_base.head(200), width="stretch", hide_index=True)
