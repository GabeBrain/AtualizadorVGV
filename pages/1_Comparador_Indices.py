from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from src.comparador_component import render_comparador_workspace
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

FILTER_EMP_KEY = "__persist_comparador_filter_empreendimentos"
FILTER_CITY_KEY = "__persist_comparador_filter_cidades"
FILTER_TIPO_KEY = "__persist_comparador_filter_tipologias"
FILTER_STATUS_KEY = "__persist_comparador_filter_status"
COMPARE_LAST_TOKEN_KEY = "__comparador_last_source_token"

PALETTE = {
    "brain_primary": "#5B7537",
    "brain_secondary": "#587030",
    "brain_highlight": "#F8D000",
    "bg": "#F7F8FA",
    "surface": "#FFFFFF",
    "text": "#111827",
    "muted": "#6B7280",
    "line": "#E5E7EB",
    "soft": "#EEF2E4",
}

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
    allowed = set(options)
    st.session_state[key] = [value for value in current if value in allowed]


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return text


def _as_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


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


def _build_component_rows(
    base_frame: pd.DataFrame,
    empreendimento_col: str,
    cidade_col: str | None,
    tipologia_col: str | None,
    status_col: str | None,
    latitude_col: str | None,
    longitude_col: str | None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for _, row in base_frame.iterrows():
        lat_value = _as_float(row.get(latitude_col)) if latitude_col else None
        lon_value = _as_float(row.get(longitude_col)) if longitude_col else None
        row_id_raw = row.get("__registro_id")

        row_id: int | None = None
        try:
            if row_id_raw is not None and not (isinstance(row_id_raw, float) and pd.isna(row_id_raw)):
                row_id = int(row_id_raw)
        except (TypeError, ValueError):
            row_id = None

        rows.append(
            {
                "id": row_id,
                "empreendimento": _safe_text(row.get(empreendimento_col)),
                "cidade": _safe_text(row.get(cidade_col)) if cidade_col else "",
                "tipologia": _safe_text(row.get(tipologia_col)) if tipologia_col else "",
                "status": _safe_text(row.get(status_col)) if status_col else "",
                "lat": lat_value,
                "lon": lon_value,
            }
        )

    return rows


def _apply_filters(
    source_df: pd.DataFrame,
    empreendimento_col: str,
    cidade_col: str | None,
    tipologia_col: str | None,
    status_col: str | None,
) -> pd.DataFrame:
    filtered = source_df.copy()

    selected_emp = st.session_state.get(FILTER_EMP_KEY, []) or []
    selected_city = st.session_state.get(FILTER_CITY_KEY, []) or []
    selected_tipo = st.session_state.get(FILTER_TIPO_KEY, []) or []
    selected_status = st.session_state.get(FILTER_STATUS_KEY, []) or []

    if selected_emp:
        filtered = filtered[filtered[empreendimento_col].astype(str).isin(selected_emp)]
    if cidade_col and selected_city:
        filtered = filtered[filtered[cidade_col].astype(str).isin(selected_city)]
    if tipologia_col and selected_tipo:
        filtered = filtered[filtered[tipologia_col].astype(str).isin(selected_tipo)]
    if status_col and selected_status:
        filtered = filtered[filtered[status_col].astype(str).isin(selected_status)]

    return filtered


st.title(APP_NAME)
st.caption("Workspace V1 com filtro interativo + mapa reativo (estado independente desta pagina).")

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

if st.session_state.get(COMPARE_LAST_TOKEN_KEY) != shared_token:
    st.session_state[COMPARE_LAST_TOKEN_KEY] = shared_token
    st.session_state[FILTER_EMP_KEY] = []
    st.session_state[FILTER_CITY_KEY] = []
    st.session_state[FILTER_TIPO_KEY] = []
    st.session_state[FILTER_STATUS_KEY] = []

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
latitude_col = _find_column(list(base_enriched.columns), ["Latitude"])
longitude_col = _find_column(list(base_enriched.columns), ["Longitude"])

if not empreendimento_col:
    st.error("A coluna 'Empreendimento' e obrigatoria para o comparador.")
    st.stop()

for key in (FILTER_EMP_KEY, FILTER_CITY_KEY, FILTER_TIPO_KEY, FILTER_STATUS_KEY):
    st.session_state.setdefault(key, [])

emp_options = _options_for_column(base_enriched, empreendimento_col)
city_options = _options_for_column(base_enriched, cidade_col)
tipo_options = _options_for_column(base_enriched, tipologia_col)
status_options = _options_for_column(base_enriched, status_col)

_sanitize_filter_state(FILTER_EMP_KEY, emp_options)
_sanitize_filter_state(FILTER_CITY_KEY, city_options)
_sanitize_filter_state(FILTER_TIPO_KEY, tipo_options)
_sanitize_filter_state(FILTER_STATUS_KEY, status_options)

selected_filters = {
    "empreendimentos": list(st.session_state[FILTER_EMP_KEY]),
    "cidades": list(st.session_state[FILTER_CITY_KEY]),
    "tipologias": list(st.session_state[FILTER_TIPO_KEY]),
    "status": list(st.session_state[FILTER_STATUS_KEY]),
}

component_payload = {
    "summary": {
        "rows": int(len(base_enriched)),
        "empreendimentos": int(base_enriched[empreendimento_col].astype(str).nunique()),
    },
    "rows": _build_component_rows(
        base_enriched,
        empreendimento_col,
        cidade_col,
        tipologia_col,
        status_col,
        latitude_col,
        longitude_col,
    ),
    "options": {
        "empreendimentos": emp_options,
        "cidades": city_options,
        "tipologias": tipo_options,
        "status": status_options,
    },
    "selectedFilters": selected_filters,
    "palette": PALETTE,
}

component_event = render_comparador_workspace(
    payload=component_payload,
    key=f"comparador_workspace_{shared_token}",
)

if isinstance(component_event, dict):
    event_filters = component_event.get("filters")
    if isinstance(event_filters, dict):
        filter_targets = [
            ("empreendimentos", FILTER_EMP_KEY, set(emp_options)),
            ("cidades", FILTER_CITY_KEY, set(city_options)),
            ("tipologias", FILTER_TIPO_KEY, set(tipo_options)),
            ("status", FILTER_STATUS_KEY, set(status_options)),
        ]

        has_change = False
        for event_key, state_key, allowed_values in filter_targets:
            incoming = event_filters.get(event_key)
            if not isinstance(incoming, list):
                continue

            sanitized = [str(value) for value in incoming if str(value) in allowed_values]
            if sanitized != st.session_state[state_key]:
                st.session_state[state_key] = sanitized
                has_change = True

        if has_change:
            st.rerun()

filtered_df = _apply_filters(
    source_df=base_enriched,
    empreendimento_col=empreendimento_col,
    cidade_col=cidade_col,
    tipologia_col=tipologia_col,
    status_col=status_col,
)

st.success(f"Fonte compartilhada ativa: {shared_source_name}")
st.caption(f"Registros apos filtros (workspace V1): {len(filtered_df)}")
st.subheader("Dataframe resultante dos filtros")
st.dataframe(filtered_df, width="stretch", hide_index=True)
