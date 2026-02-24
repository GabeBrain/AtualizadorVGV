from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from src.theme import apply_brain_theme, render_sidebar_menu
from src.vgv_core import clean_options as core_clean_options
from src.vgv_core import find_column as core_find_column
from src.vgv_core import source_token as core_source_token
from src.vgv_parser import parse_vgv_workbook

APP_NAME = "Comparador de Índices"
SHARED_SOURCE_TOKEN_KEY = "__shared_source_token"
SHARED_SOURCE_NAME_KEY = "__shared_source_name"
SHARED_BASE_DF_KEY = "__shared_base_df"
SHARED_PERF_DF_KEY = "__shared_perf_df"
SHARED_METADATA_KEY = "__shared_metadata"

FILTER_EMP_KEY = "comparador_filter_empreendimentos"
FILTER_CITY_KEY = "comparador_filter_cidades"
FILTER_TIPO_KEY = "comparador_filter_tipologias"
FILTER_STATUS_KEY = "comparador_filter_status"
FILTER_EMP_WIDGET_KEY = "__widget_comparador_filter_empreendimentos"
FILTER_CITY_WIDGET_KEY = "__widget_comparador_filter_cidades"
FILTER_TIPO_WIDGET_KEY = "__widget_comparador_filter_tipologias"
FILTER_STATUS_WIDGET_KEY = "__widget_comparador_filter_status"
COMPARE_LAST_TOKEN_KEY = "__comparador_last_source_token"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon=":balance_scale:")
apply_brain_theme()
render_sidebar_menu()


@st.cache_data(show_spinner=False)
def _parse_uploaded(file_bytes: bytes):
    return parse_vgv_workbook(BytesIO(file_bytes))


@st.cache_data(show_spinner=False)
def _parse_sample(path_text: str):
    return parse_vgv_workbook(path_text)


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    return core_find_column(columns, candidates)


def _options_for_column(df: pd.DataFrame, column: str | None) -> list[str]:
    if not column or column not in df.columns:
        return []
    return core_clean_options(df[column])


def _sanitize_filter_state(key: str, options: list[str]) -> None:
    current = st.session_state.get(key, []) or []
    st.session_state[key] = [value for value in current if value in options]


def _sync_filter_from_widget(state_key: str, widget_key: str) -> None:
    st.session_state[state_key] = list(st.session_state.get(widget_key, []) or [])


def _rehydrate_shared_source_if_needed() -> tuple[str | None, str, pd.DataFrame | None, pd.DataFrame | None]:
    shared_token = st.session_state.get(SHARED_SOURCE_TOKEN_KEY)
    shared_source_name = st.session_state.get(SHARED_SOURCE_NAME_KEY) or "-"
    shared_base_df = st.session_state.get(SHARED_BASE_DF_KEY)
    shared_perf_df = st.session_state.get(SHARED_PERF_DF_KEY)

    if shared_token is not None and isinstance(shared_base_df, pd.DataFrame):
        perf_df = shared_perf_df if isinstance(shared_perf_df, pd.DataFrame) else None
        return shared_token, shared_source_name, shared_base_df, perf_df

    sample_path = Path(__file__).resolve().parents[1] / "assets" / "tabelaEmpreendimentoReduzida.xlsx"
    source_mode = st.session_state.get("source_mode")
    source_name = st.session_state.get("source_name")
    source_bytes = st.session_state.get("source_bytes")

    source_token = core_source_token(source_mode, source_name, source_bytes, sample_path)
    if source_token is None:
        return None, "-", None, None

    try:
        if source_mode == "upload" and source_bytes:
            base_df, perf_df, metadata = _parse_uploaded(source_bytes)
        elif source_mode == "sample" and sample_path.exists():
            base_df, perf_df, metadata = _parse_sample(str(sample_path))
        else:
            return None, "-", None, None
    except Exception as exc:
        st.error(f"Falha ao recuperar a fonte compartilhada: {exc}")
        st.stop()

    st.session_state[SHARED_SOURCE_TOKEN_KEY] = source_token
    st.session_state[SHARED_SOURCE_NAME_KEY] = source_name or "-"
    st.session_state[SHARED_BASE_DF_KEY] = base_df.copy()
    st.session_state[SHARED_PERF_DF_KEY] = perf_df.copy()
    st.session_state[SHARED_METADATA_KEY] = dict(metadata)

    return source_token, (source_name or "-"), base_df, perf_df


st.title(APP_NAME)
st.caption("Esta pagina usa a mesma fonte da pagina Atualizador de VGV, com filtros independentes.")

shared_token, shared_source_name, shared_base_df, shared_perf_df = _rehydrate_shared_source_if_needed()

if shared_token is None or shared_base_df is None:
    st.warning("Nenhum arquivo ativo. Carregue a planilha na pagina Atualizador de VGV.")
    st.stop()

if not isinstance(shared_base_df, pd.DataFrame):
    st.error("O dataset compartilhado esta invalido. Recarregue a planilha na pagina principal.")
    st.stop()

if shared_perf_df is not None and not isinstance(shared_perf_df, pd.DataFrame):
    st.error("O dataset de performance compartilhado esta invalido. Recarregue a planilha na pagina principal.")
    st.stop()

# Reset somente quando a fonte ativa muda. Navegar entre paginas preserva os filtros.
if st.session_state.get(COMPARE_LAST_TOKEN_KEY) != shared_token:
    st.session_state[COMPARE_LAST_TOKEN_KEY] = shared_token
    st.session_state[FILTER_EMP_KEY] = []
    st.session_state[FILTER_CITY_KEY] = []
    st.session_state[FILTER_TIPO_KEY] = []
    st.session_state[FILTER_STATUS_KEY] = []
    st.session_state[FILTER_EMP_WIDGET_KEY] = []
    st.session_state[FILTER_CITY_WIDGET_KEY] = []
    st.session_state[FILTER_TIPO_WIDGET_KEY] = []
    st.session_state[FILTER_STATUS_WIDGET_KEY] = []

base_enriched = shared_base_df.copy()

status_metric_col = None
if isinstance(shared_perf_df, pd.DataFrame) and not shared_perf_df.empty:
    status_metric_col = _find_column(list(shared_perf_df.columns), ["Status"])

    if status_metric_col and "__registro_id" in shared_perf_df.columns and "__registro_id" in base_enriched.columns:
        latest_record = shared_perf_df.copy()
        if "MesData" in latest_record.columns:
            ordered = latest_record.dropna(subset=["MesData"]).sort_values("MesData")
            if not ordered.empty:
                latest_record = ordered

        latest_record = latest_record.groupby("__registro_id", as_index=False).tail(1)
        status_frame = latest_record[["__registro_id", status_metric_col]].rename(
            columns={status_metric_col: "Status Atual"}
        )
        base_enriched = base_enriched.merge(status_frame, on="__registro_id", how="left")

empreendimento_col = _find_column(list(base_enriched.columns), ["Empreendimento"])
cidade_col = _find_column(list(base_enriched.columns), ["Cidade"])
tipologia_col = _find_column(list(base_enriched.columns), ["Tipologia"])
status_col = "Status Atual" if "Status Atual" in base_enriched.columns else None

if not empreendimento_col:
    st.error("A coluna 'Empreendimento' e obrigatoria para o comparador.")
    st.stop()

for key in (FILTER_EMP_KEY, FILTER_CITY_KEY, FILTER_TIPO_KEY, FILTER_STATUS_KEY):
    st.session_state.setdefault(key, [])
for state_key, widget_key in (
    (FILTER_EMP_KEY, FILTER_EMP_WIDGET_KEY),
    (FILTER_CITY_KEY, FILTER_CITY_WIDGET_KEY),
    (FILTER_TIPO_KEY, FILTER_TIPO_WIDGET_KEY),
    (FILTER_STATUS_KEY, FILTER_STATUS_WIDGET_KEY),
):
    st.session_state.setdefault(widget_key, list(st.session_state.get(state_key, [])))

emp_options = _options_for_column(base_enriched, empreendimento_col)
city_options = _options_for_column(base_enriched, cidade_col)
tipo_options = _options_for_column(base_enriched, tipologia_col)
status_options = _options_for_column(base_enriched, status_col)

_sanitize_filter_state(FILTER_EMP_KEY, emp_options)
_sanitize_filter_state(FILTER_CITY_KEY, city_options)
_sanitize_filter_state(FILTER_TIPO_KEY, tipo_options)
_sanitize_filter_state(FILTER_STATUS_KEY, status_options)

st.session_state[FILTER_EMP_WIDGET_KEY] = list(st.session_state[FILTER_EMP_KEY])
st.session_state[FILTER_CITY_WIDGET_KEY] = list(st.session_state[FILTER_CITY_KEY])
st.session_state[FILTER_TIPO_WIDGET_KEY] = list(st.session_state[FILTER_TIPO_KEY])
st.session_state[FILTER_STATUS_WIDGET_KEY] = list(st.session_state[FILTER_STATUS_KEY])

st.success(f"Fonte compartilhada ativa: {shared_source_name}")
st.subheader("Filtros")

f1, f2, f3, f4 = st.columns(4)
with f1:
    st.multiselect(
        "Empreendimento",
        options=emp_options,
        key=FILTER_EMP_WIDGET_KEY,
        on_change=_sync_filter_from_widget,
        args=(FILTER_EMP_KEY, FILTER_EMP_WIDGET_KEY),
    )
with f2:
    st.multiselect(
        "Cidade",
        options=city_options,
        key=FILTER_CITY_WIDGET_KEY,
        disabled=not city_options,
        on_change=_sync_filter_from_widget,
        args=(FILTER_CITY_KEY, FILTER_CITY_WIDGET_KEY),
    )
with f3:
    st.multiselect(
        "Tipologia",
        options=tipo_options,
        key=FILTER_TIPO_WIDGET_KEY,
        disabled=not tipo_options,
        on_change=_sync_filter_from_widget,
        args=(FILTER_TIPO_KEY, FILTER_TIPO_WIDGET_KEY),
    )
with f4:
    st.multiselect(
        "Status Atual",
        options=status_options,
        key=FILTER_STATUS_WIDGET_KEY,
        disabled=not status_options,
        on_change=_sync_filter_from_widget,
        args=(FILTER_STATUS_KEY, FILTER_STATUS_WIDGET_KEY),
    )

filtered_df = base_enriched.copy()

selected_emp = st.session_state[FILTER_EMP_KEY]
selected_city = st.session_state[FILTER_CITY_KEY]
selected_tipo = st.session_state[FILTER_TIPO_KEY]
selected_status = st.session_state[FILTER_STATUS_KEY]

if selected_emp:
    filtered_df = filtered_df[filtered_df[empreendimento_col].astype(str).isin(selected_emp)]
if cidade_col and selected_city:
    filtered_df = filtered_df[filtered_df[cidade_col].astype(str).isin(selected_city)]
if tipologia_col and selected_tipo:
    filtered_df = filtered_df[filtered_df[tipologia_col].astype(str).isin(selected_tipo)]
if status_col and selected_status:
    filtered_df = filtered_df[filtered_df[status_col].astype(str).isin(selected_status)]

st.caption(f"Registros apos filtros: {len(filtered_df)}")
st.subheader("Dataframe resultante dos filtros")
st.dataframe(filtered_df, width="stretch", hide_index=True)
