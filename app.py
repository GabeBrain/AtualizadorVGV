from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.theme import apply_brain_theme, render_sidebar_menu
from src.vgv_core import (
    build_reajuste_dataset as core_build_reajuste_dataset,
    clean_options as core_clean_options,
    display_value_text as core_display_value_text,
    find_column as core_find_column,
    format_brl as core_format_brl,
    format_brl_compact as core_format_brl_compact,
    format_decimal as core_format_decimal,
    format_number as core_format_number,
    map_style_light as core_map_style_light,
    selection_index_from_event as core_selection_index_from_event,
    selection_name_from_event as core_selection_name_from_event,
    source_token as core_source_token,
    status_color as core_status_color,
    to_excel_bytes as core_to_excel_bytes,
)
from src.vgv_parser import extract_present_amenities, normalize_text, parse_vgv_workbook

APP_NAME = "Atualizador de VGV"
REAJUSTE_BASE_DATE = pd.Timestamp("2025-12-01")
REAJUSTE_INDEX_ORDER = ("INCC-DI", "IPCA", "IGP-DI")
REAJUSTE_INDEX_FILE_MAP = {
    "INCC-DI": ("INCC_Series_MeDI.xlsx", "INCC-DI"),
    "IPCA": ("343b-serie-historica-ipca-ibge.xlsx", "Plan1"),
    "IGP-DI": ("8dec-serie-historica-igp-di-fgv.xlsx", "Plan1"),
}
REAJUSTE_INDEX_WIDGET_KEY = "__widget_reajuste_indices"
SHARED_SOURCE_TOKEN_KEY = "__shared_source_token"
SHARED_SOURCE_NAME_KEY = "__shared_source_name"
SHARED_BASE_DF_KEY = "__shared_base_df"
SHARED_PERF_DF_KEY = "__shared_perf_df"
SHARED_METADATA_KEY = "__shared_metadata"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon=":bar_chart:")
apply_brain_theme()
render_sidebar_menu()


@st.cache_data(show_spinner=False)
def _parse_uploaded(file_bytes: bytes):
    return parse_vgv_workbook(BytesIO(file_bytes))


@st.cache_data(show_spinner=False)
def _parse_sample(path_text: str):
    return parse_vgv_workbook(path_text)


def _spinner_with_timer(message: str):
    try:
        return st.spinner(message, show_time=True)
    except TypeError:
        return st.spinner(message)



def _source_token(
    source_mode: str | None,
    source_name: str | None,
    source_bytes: bytes | None,
    sample_path: Path,
) -> str | None:
    return core_source_token(source_mode, source_name, source_bytes, sample_path)


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    return core_find_column(columns, candidates)


def _format_number(value: Any) -> str:
    return core_format_number(value)


def _format_decimal(value: Any) -> str:
    return core_format_decimal(value)


def _format_brl(value: Any) -> str:
    return core_format_brl(value)


def _format_brl_compact(value: Any, precision: int = 1) -> str:
    return core_format_brl_compact(value, precision)


def _display_value_text(value: Any) -> str:
    return core_display_value_text(value)


@st.cache_data(show_spinner=False)
def _to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    return core_to_excel_bytes(sheets)


def _selection_index_from_event(event: Any) -> int | None:
    return core_selection_index_from_event(event)


def _selection_name_from_event(event: Any) -> str | None:
    return core_selection_name_from_event(event)


def _clean_options(series: pd.Series) -> list[str]:
    return core_clean_options(series)


def _status_color(status_value: Any) -> list[int]:
    return core_status_color(status_value)


def _map_style_light() -> str:
    return core_map_style_light(pdk)


@st.cache_data(show_spinner=False)
def _build_reajuste_dataset(
    perf_source: pd.DataFrame,
    incc_path_text: str,
    target_months: tuple[str, ...] | None,
    base_date_text: str,
    extra_index_sources: tuple[tuple[str, str, str], ...] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    return core_build_reajuste_dataset(
        perf_source=perf_source,
        incc_path_text=incc_path_text,
        target_months=target_months,
        base_date_text=base_date_text,
        fallback_base_date=REAJUSTE_BASE_DATE,
        extra_index_sources=extra_index_sources,
    )


st.title(APP_NAME)
st.caption("Mapa, séries mensais, ficha do empreendimento e amenidades em uma única página.")

sample_path = Path(__file__).resolve().parent / "assets" / "tabelaEmpreendimentoReduzida.xlsx"

with st.expander("Fonte de dados", expanded=True):
    uploaded_file = st.file_uploader("Planilha no formato padrão", type=["xlsx", "xls"])
    b1, b2, _ = st.columns([1, 1, 2])
    use_sample = b1.button(
        "Usar exemplo de assets",
        width="stretch",
        disabled=not sample_path.exists(),
    )
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
            "__loaded_source_token",
            SHARED_SOURCE_TOKEN_KEY,
            SHARED_SOURCE_NAME_KEY,
            SHARED_BASE_DF_KEY,
            SHARED_PERF_DF_KEY,
            SHARED_METADATA_KEY,
            "selected_empreendimento",
            "filter_empreendimentos",
            "filter_cidades",
            "filter_tipologias",
            "filter_status",
            "__persist_filter_empreendimentos",
            "__persist_filter_cidades",
            "__persist_filter_tipologias",
            "__persist_filter_status",
            "__widget_filter_empreendimentos",
            "__widget_filter_cidades",
            "__widget_filter_tipologias",
            "__widget_filter_status",
            "__pending_map_filter",
            REAJUSTE_INDEX_WIDGET_KEY,
        ):
            st.session_state.pop(key, None)

if "source_mode" not in st.session_state and sample_path.exists():
    st.session_state["source_mode"] = "sample"
    st.session_state["source_name"] = sample_path.name

source_mode = st.session_state.get("source_mode")
base_df: pd.DataFrame | None = None
perf_df: pd.DataFrame | None = None
metadata: dict[str, Any] | None = None
source_token = _source_token(
    source_mode,
    st.session_state.get("source_name"),
    st.session_state.get("source_bytes"),
    sample_path,
)
is_new_source = source_token is not None and st.session_state.get("__loaded_source_token") != source_token

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
    st.info("Carregue uma planilha para iniciar a análise.")
    st.stop()

if source_token is not None:
    st.session_state["__loaded_source_token"] = source_token
    st.session_state[SHARED_SOURCE_TOKEN_KEY] = source_token
    st.session_state[SHARED_SOURCE_NAME_KEY] = st.session_state.get("source_name")
    st.session_state[SHARED_BASE_DF_KEY] = base_df.copy()
    st.session_state[SHARED_PERF_DF_KEY] = perf_df.copy()
    st.session_state[SHARED_METADATA_KEY] = dict(metadata)

if base_df.empty:
    st.warning("A planilha não possui linhas de dados após a limpeza inicial.")
    st.stop()

month_labels = metadata.get("month_labels", [])
amenity_columns = metadata.get("amenity_columns", [])

st.success(
    f"Fonte ativa: {st.session_state.get('source_name', '-') } | "
    f"Registros: {len(base_df)} | Meses detectados: {len(month_labels)}"
)

empreendimento_col = _find_column(list(base_df.columns), ["Empreendimento"])
cidade_col = _find_column(list(base_df.columns), ["Cidade"])
estado_col = _find_column(list(base_df.columns), ["Estado"])
latitude_col = _find_column(list(base_df.columns), ["Latitude"])
longitude_col = _find_column(list(base_df.columns), ["Longitude"])
tipologia_col = _find_column(list(base_df.columns), ["Tipologia"])

if not empreendimento_col:
    st.error("A coluna 'Empreendimento' é obrigatória para a análise.")
    st.stop()

status_metric_col = _find_column(list(perf_df.columns), ["Status"])
vgv_total_col = _find_column(list(perf_df.columns), ["VGV Total"])
vgv_oferta_col = _find_column(list(perf_df.columns), ["VGV Oferta Final"])
estoque_col = _find_column(list(perf_df.columns), ["Estoque"])
vendas_col = _find_column(list(perf_df.columns), ["Vendas"])
preco_col = _find_column(list(perf_df.columns), ["Preco"])
preco_lanc_col = _find_column(list(perf_df.columns), ["Preco de Lancamento", "Preco de Lan?amento"])

reajuste_perf = pd.DataFrame()
reajuste_meta: dict[str, Any] = {}
reajuste_error: str | None = None
assets_dir = Path(__file__).resolve().parent / "assets"
incc_series_path = assets_dir / REAJUSTE_INDEX_FILE_MAP["INCC-DI"][0]
extra_index_sources: tuple[tuple[str, str, str], ...] = tuple(
    (index_name, str(assets_dir / file_name), sheet_name)
    for index_name in REAJUSTE_INDEX_ORDER
    if index_name != "INCC-DI"
    for file_name, sheet_name in [REAJUSTE_INDEX_FILE_MAP[index_name]]
)

reajuste_target_months: tuple[str, ...] | None = tuple(month_labels) if month_labels else None

try:
    if is_new_source:
        with _spinner_with_timer("Calculando reajuste por índice..."):
            reajuste_perf, reajuste_meta = _build_reajuste_dataset(
                perf_df,
                str(incc_series_path),
                reajuste_target_months,
                REAJUSTE_BASE_DATE.strftime("%Y-%m-%d"),
                extra_index_sources=extra_index_sources,
            )
    else:
        reajuste_perf, reajuste_meta = _build_reajuste_dataset(
            perf_df,
            str(incc_series_path),
            reajuste_target_months,
            REAJUSTE_BASE_DATE.strftime("%Y-%m-%d"),
            extra_index_sources=extra_index_sources,
        )
except Exception as exc:
    reajuste_error = f"Falha ao preparar reajuste por índice: {exc}"

if not reajuste_error and not reajuste_meta.get("available_indices"):
    reajuste_error = (
        "Nenhum arquivo de índice encontrado em assets "
        "(INCC, IPCA ou IGP-DI)."
    )

latest_record = pd.DataFrame(columns=["__registro_id"])
if not perf_df.empty and "MesData" in perf_df.columns:
    latest_record = (
        perf_df.dropna(subset=["MesData"]).sort_values("MesData").groupby("__registro_id", as_index=False).tail(1)
    )

base_enriched = base_df.copy()
if not latest_record.empty and status_metric_col and status_metric_col in latest_record.columns:
    status_frame = latest_record[["__registro_id", status_metric_col]].rename(
        columns={status_metric_col: "Status Atual"}
    )
    base_enriched = base_enriched.merge(status_frame, on="__registro_id", how="left")

FILTER_EMP_KEY = "__persist_filter_empreendimentos"
FILTER_CITY_KEY = "__persist_filter_cidades"
FILTER_TIPO_KEY = "__persist_filter_tipologias"
FILTER_STATUS_KEY = "__persist_filter_status"
FILTER_EMP_WIDGET_KEY = "__widget_filter_empreendimentos"
FILTER_CITY_WIDGET_KEY = "__widget_filter_cidades"
FILTER_TIPO_WIDGET_KEY = "__widget_filter_tipologias"
FILTER_STATUS_WIDGET_KEY = "__widget_filter_status"
PENDING_MAP_FILTER_KEY = "__pending_map_filter"

for key in (FILTER_EMP_KEY, FILTER_CITY_KEY, FILTER_TIPO_KEY, FILTER_STATUS_KEY):
    st.session_state.setdefault(key, [])
st.session_state.setdefault(PENDING_MAP_FILTER_KEY, None)
for state_key, widget_key in (
    (FILTER_EMP_KEY, FILTER_EMP_WIDGET_KEY),
    (FILTER_CITY_KEY, FILTER_CITY_WIDGET_KEY),
    (FILTER_TIPO_KEY, FILTER_TIPO_WIDGET_KEY),
    (FILTER_STATUS_KEY, FILTER_STATUS_WIDGET_KEY),
):
    st.session_state.setdefault(widget_key, list(st.session_state.get(state_key, [])))


st.subheader("Filtros")
st.caption("Sem seleção em um filtro = todos os registros daquele campo.")

all_empreendimento_options = _clean_options(base_enriched[empreendimento_col])

pending_map_filter = st.session_state.get(PENDING_MAP_FILTER_KEY)
if pending_map_filter is not None:
    pending_name = str(pending_map_filter).strip()
    st.session_state[FILTER_EMP_KEY] = [pending_name] if pending_name in all_empreendimento_options else []
    st.session_state[FILTER_CITY_KEY] = []
    st.session_state[FILTER_TIPO_KEY] = []
    st.session_state[FILTER_STATUS_KEY] = []
    st.session_state["selected_empreendimento"] = pending_name or None
    st.session_state[PENDING_MAP_FILTER_KEY] = None


def _sanitize_filter_state(key: str, options: list[str]) -> None:
    current = st.session_state.get(key, []) or []
    st.session_state[key] = [value for value in current if value in options]


def _sync_filter_from_widget(state_key: str, widget_key: str) -> None:
    st.session_state[state_key] = list(st.session_state.get(widget_key, []) or [])


def _filter_with_current_state(exclude_key: str | None = None) -> pd.DataFrame:
    scoped = base_enriched.copy()

    if exclude_key != FILTER_EMP_KEY and st.session_state[FILTER_EMP_KEY]:
        scoped = scoped[scoped[empreendimento_col].astype(str).isin(st.session_state[FILTER_EMP_KEY])]

    if cidade_col and exclude_key != FILTER_CITY_KEY and st.session_state[FILTER_CITY_KEY]:
        scoped = scoped[scoped[cidade_col].astype(str).isin(st.session_state[FILTER_CITY_KEY])]

    if tipologia_col and exclude_key != FILTER_TIPO_KEY and st.session_state[FILTER_TIPO_KEY]:
        scoped = scoped[scoped[tipologia_col].astype(str).isin(st.session_state[FILTER_TIPO_KEY])]

    if "Status Atual" in scoped.columns and exclude_key != FILTER_STATUS_KEY and st.session_state[FILTER_STATUS_KEY]:
        scoped = scoped[scoped["Status Atual"].astype(str).isin(st.session_state[FILTER_STATUS_KEY])]

    return scoped


def _build_filter_options() -> dict[str, list[str]]:
    emp_scoped = _filter_with_current_state(exclude_key=FILTER_EMP_KEY)
    city_scoped = _filter_with_current_state(exclude_key=FILTER_CITY_KEY)
    tip_scoped = _filter_with_current_state(exclude_key=FILTER_TIPO_KEY)
    status_scoped = _filter_with_current_state(exclude_key=FILTER_STATUS_KEY)

    return {
        FILTER_EMP_KEY: _clean_options(emp_scoped[empreendimento_col]),
        FILTER_CITY_KEY: _clean_options(city_scoped[cidade_col]) if cidade_col else [],
        FILTER_TIPO_KEY: _clean_options(tip_scoped[tipologia_col]) if tipologia_col else [],
        FILTER_STATUS_KEY: _clean_options(status_scoped["Status Atual"]) if "Status Atual" in status_scoped.columns else [],
    }


filter_options = _build_filter_options()
for _ in range(2):
    _sanitize_filter_state(FILTER_EMP_KEY, filter_options[FILTER_EMP_KEY])
    _sanitize_filter_state(FILTER_CITY_KEY, filter_options[FILTER_CITY_KEY])
    _sanitize_filter_state(FILTER_TIPO_KEY, filter_options[FILTER_TIPO_KEY])
    _sanitize_filter_state(FILTER_STATUS_KEY, filter_options[FILTER_STATUS_KEY])
    filter_options = _build_filter_options()

st.session_state[FILTER_EMP_WIDGET_KEY] = list(st.session_state[FILTER_EMP_KEY])
st.session_state[FILTER_CITY_WIDGET_KEY] = list(st.session_state[FILTER_CITY_KEY])
st.session_state[FILTER_TIPO_WIDGET_KEY] = list(st.session_state[FILTER_TIPO_KEY])
st.session_state[FILTER_STATUS_WIDGET_KEY] = list(st.session_state[FILTER_STATUS_KEY])

fc1, fc2, fc3, fc4 = st.columns(4)
fc1.multiselect(
    "Empreendimento",
    options=filter_options[FILTER_EMP_KEY],
    key=FILTER_EMP_WIDGET_KEY,
    on_change=_sync_filter_from_widget,
    args=(FILTER_EMP_KEY, FILTER_EMP_WIDGET_KEY),
)
fc2.multiselect(
    "Cidade",
    options=filter_options[FILTER_CITY_KEY],
    key=FILTER_CITY_WIDGET_KEY,
    on_change=_sync_filter_from_widget,
    args=(FILTER_CITY_KEY, FILTER_CITY_WIDGET_KEY),
)
fc3.multiselect(
    "Tipologia",
    options=filter_options[FILTER_TIPO_KEY],
    key=FILTER_TIPO_WIDGET_KEY,
    on_change=_sync_filter_from_widget,
    args=(FILTER_TIPO_KEY, FILTER_TIPO_WIDGET_KEY),
)
fc4.multiselect(
    "Status atual",
    options=filter_options[FILTER_STATUS_KEY],
    key=FILTER_STATUS_WIDGET_KEY,
    on_change=_sync_filter_from_widget,
    args=(FILTER_STATUS_KEY, FILTER_STATUS_WIDGET_KEY),
)

selected_empreendimentos = st.session_state[FILTER_EMP_KEY]
selected_cities = st.session_state[FILTER_CITY_KEY]
selected_tipologias = st.session_state[FILTER_TIPO_KEY]
selected_status = st.session_state[FILTER_STATUS_KEY]

filtered_base = base_enriched.copy()
if selected_empreendimentos:
    filtered_base = filtered_base[filtered_base[empreendimento_col].astype(str).isin(selected_empreendimentos)]
if cidade_col and selected_cities:
    filtered_base = filtered_base[filtered_base[cidade_col].astype(str).isin(selected_cities)]
if tipologia_col and selected_tipologias:
    filtered_base = filtered_base[filtered_base[tipologia_col].astype(str).isin(selected_tipologias)]
if "Status Atual" in filtered_base.columns and selected_status:
    filtered_base = filtered_base[filtered_base["Status Atual"].astype(str).isin(selected_status)]

if filtered_base.empty:
    st.warning("Nenhum registro encontrado com os filtros selecionados.")
    st.stop()

filtered_ids = set(filtered_base["__registro_id"].tolist())
filtered_perf = perf_df[perf_df["__registro_id"].isin(filtered_ids)].copy()
filtered_reajuste = (
    reajuste_perf[reajuste_perf["__registro_id"].isin(filtered_ids)].copy()
    if not reajuste_perf.empty
    else pd.DataFrame()
)

filtered_empreendimentos = _clean_options(filtered_base[empreendimento_col])

# Mapa
st.subheader("Mapa de empreendimentos")
st.caption("Clique em um ponto do mapa para filtrar automaticamente aquele empreendimento.")

map_base = filtered_base.copy()
if latitude_col and longitude_col:
    map_base["__lat"] = pd.to_numeric(map_base[latitude_col], errors="coerce")
    map_base["__lon"] = pd.to_numeric(map_base[longitude_col], errors="coerce")
else:
    map_base["__lat"] = pd.NA
    map_base["__lon"] = pd.NA

map_base = map_base.dropna(subset=["__lat", "__lon"])

if map_base.empty:
    st.warning("Não há coordenadas válidas para exibir o mapa com os filtros atuais.")
else:
    latest_by_empreendimento = pd.DataFrame(columns=[empreendimento_col])
    if not filtered_perf.empty and "MesData" in filtered_perf.columns:
        agg_map: dict[str, str] = {}
        if vgv_total_col:
            agg_map[vgv_total_col] = "sum"
        if vgv_oferta_col:
            agg_map[vgv_oferta_col] = "sum"
        if vendas_col:
            agg_map[vendas_col] = "sum"
        if estoque_col:
            agg_map[estoque_col] = "sum"

        status_latest_frame = pd.DataFrame(columns=[empreendimento_col, "Status Mapa", "Mes Mapa"])
        if status_metric_col and status_metric_col in filtered_perf.columns:
            status_latest_frame = (
                filtered_perf.dropna(subset=["MesData"])
                .sort_values("MesData")
                .groupby(empreendimento_col, as_index=False)
                .tail(1)[[empreendimento_col, "Mes", status_metric_col]]
                .rename(columns={"Mes": "Mes Mapa", status_metric_col: "Status Mapa"})
            )

        if agg_map:
            month_level = (
                filtered_perf.groupby([empreendimento_col, "Mes", "MesData"], as_index=False)
                .agg(agg_map)
                .sort_values("MesData")
            )
            latest_by_empreendimento = (
                month_level.groupby(empreendimento_col, as_index=False)
                .tail(1)
                .rename(columns={"Mes": "Mes Mapa"})
            )
            if not status_latest_frame.empty:
                latest_by_empreendimento = latest_by_empreendimento.merge(
                    status_latest_frame[[empreendimento_col, "Status Mapa"]],
                    on=empreendimento_col,
                    how="left",
                )
        else:
            latest_by_empreendimento = status_latest_frame

    agg_fields: dict[str, Any] = {"__lat": "mean", "__lon": "mean"}
    if cidade_col:
        agg_fields[cidade_col] = "first"
    if estado_col:
        agg_fields[estado_col] = "first"

    points = (
        map_base.groupby(empreendimento_col, as_index=False)
        .agg(agg_fields)
        .rename(columns={empreendimento_col: "Empreendimento"})
    )

    if not latest_by_empreendimento.empty:
        latest_renamed = latest_by_empreendimento.rename(columns={empreendimento_col: "Empreendimento"})
        points = points.merge(latest_renamed, on="Empreendimento", how="left")

    points["Status Mapa"] = points.get("Status Mapa", pd.Series([None] * len(points))).astype("string")
    points["__color"] = points["Status Mapa"].map(_status_color)

    if vgv_oferta_col and vgv_oferta_col in points.columns:
        metric_values = pd.to_numeric(points[vgv_oferta_col], errors="coerce").fillna(0)
        if float(metric_values.max()) > float(metric_values.min()):
            norm = (metric_values - metric_values.min()) / (metric_values.max() - metric_values.min())
            points["__radius"] = 220 + norm * 260
        else:
            points["__radius"] = 260
        points["VGV Oferta Final formatado"] = metric_values.map(_format_brl)
    else:
        points["__radius"] = 260
        points["VGV Oferta Final formatado"] = "-"

    center_lat = float(points["__lat"].mean())
    center_lon = float(points["__lon"].mean())

    tooltip_parts = ["<b>{Empreendimento}</b>"]
    if cidade_col:
        tooltip_parts.append(f"{cidade_col}: {{{cidade_col}}}")
    tooltip_parts.append("Status: {Status Mapa}")
    tooltip_parts.append("Mes: {Mes Mapa}")
    tooltip_parts.append("VGV Oferta: {VGV Oferta Final formatado}")

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=points,
        get_position="[__lon, __lat]",
        get_fill_color="__color",
        get_radius="__radius",
        pickable=True,
        auto_highlight=True,
        radius_min_pixels=3,
        radius_max_pixels=12,
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=10.2, pitch=0),
        map_style=_map_style_light(),
        tooltip={"html": "<br/>".join(tooltip_parts)},
    )

    map_event = None
    try:
        map_event = st.pydeck_chart(
            deck,
            width="stretch",
            on_select="rerun",
            selection_mode="single-object",
            key="empreendimento_map",
        )
    except TypeError:
        st.pydeck_chart(deck, width="stretch", key="empreendimento_map_static")

    point_options = points["Empreendimento"].astype(str).tolist()

    if len(st.session_state[FILTER_EMP_KEY]) == 1 and st.session_state[FILTER_EMP_KEY][0] in point_options:
        st.session_state["selected_empreendimento"] = st.session_state[FILTER_EMP_KEY][0]
    elif st.session_state.get("selected_empreendimento") not in point_options:
        st.session_state["selected_empreendimento"] = point_options[0]

    event_payload = map_event if map_event is not None else st.session_state.get("empreendimento_map")

    clicked_empreendimento = _selection_name_from_event(event_payload)
    if not clicked_empreendimento:
        selected_index = _selection_index_from_event(event_payload)
        if selected_index is not None and 0 <= selected_index < len(points):
            clicked_empreendimento = str(points.iloc[selected_index]["Empreendimento"])

    if clicked_empreendimento and clicked_empreendimento in point_options:
        needs_filter_update = (
            st.session_state[FILTER_EMP_KEY] != [clicked_empreendimento]
            or bool(st.session_state[FILTER_CITY_KEY])
            or bool(st.session_state[FILTER_TIPO_KEY])
            or bool(st.session_state[FILTER_STATUS_KEY])
        )
        st.session_state["selected_empreendimento"] = clicked_empreendimento

        if needs_filter_update:
            st.session_state[PENDING_MAP_FILTER_KEY] = clicked_empreendimento
            st.rerun()

    if st.session_state.get("selected_empreendimento"):
        st.caption(f"Empreendimento em foco no mapa: {st.session_state['selected_empreendimento']}")

# Graficos temporais (sempre usando todos os meses disponiveis no arquivo)
st.subheader("Séries mensais de VGV (agregado pelos filtros)")

if filtered_perf.empty:
    st.info("Sem dados mensais para os filtros atuais.")
else:
    agg_rules: dict[str, str] = {}
    if vgv_total_col and vgv_total_col in filtered_perf.columns:
        agg_rules[vgv_total_col] = "sum"
    if vgv_oferta_col and vgv_oferta_col in filtered_perf.columns:
        agg_rules[vgv_oferta_col] = "sum"
    if vendas_col and vendas_col in filtered_perf.columns:
        agg_rules[vendas_col] = "sum"
    if estoque_col and estoque_col in filtered_perf.columns:
        agg_rules[estoque_col] = "sum"
    if preco_col and preco_col in filtered_perf.columns:
        agg_rules[preco_col] = "mean"
    if preco_lanc_col and preco_lanc_col in filtered_perf.columns:
        agg_rules[preco_lanc_col] = "mean"

    monthly = (
        filtered_perf.groupby(["Mes", "MesData"], as_index=False)
        .agg(agg_rules)
        .sort_values("MesData")
    )

    if not monthly.empty:
        k1, k2, k3, k4 = st.columns(4)
        last_row = monthly.iloc[-1]
        k1.metric("Mês de referência", str(last_row.get("Mes", "-")))
        if vgv_total_col and vgv_total_col in monthly.columns:
            k2.metric("VGV Total", _format_brl_compact(last_row.get(vgv_total_col)))
        if vgv_oferta_col and vgv_oferta_col in monthly.columns:
            k3.metric("VGV Oferta Final", _format_brl_compact(last_row.get(vgv_oferta_col)))
        if estoque_col and estoque_col in monthly.columns:
            k4.metric("Estoque", _format_number(last_row.get(estoque_col)))

        if vgv_total_col and vgv_total_col in monthly.columns and vgv_oferta_col and vgv_oferta_col in monthly.columns:
            vgv_long = monthly.melt(
                id_vars=["Mes", "MesData"],
                value_vars=[vgv_total_col, vgv_oferta_col],
                var_name="Serie",
                value_name="Valor",
            )
            series_map = {
                vgv_total_col: "VGV Total",
                vgv_oferta_col: "VGV Oferta Final",
            }
            vgv_long["Serie"] = vgv_long["Serie"].map(series_map).fillna(vgv_long["Serie"])

            vgv_chart = (
                alt.Chart(vgv_long)
                .mark_line(point=True)
                .encode(
                    x=alt.X("MesData:T", title="Mes"),
                    y=alt.Y("Valor:Q", title="Valor"),
                    color=alt.Color("Serie:N", title="Serie"),
                    tooltip=["Mes", "Serie", alt.Tooltip("Valor:Q", format=",.2f")],
                )
                .properties(height=320)
            )
            st.altair_chart(vgv_chart, width="stretch")

        if estoque_col and estoque_col in monthly.columns and vendas_col and vendas_col in monthly.columns:
            bar = (
                alt.Chart(monthly)
                .mark_bar(color="#B8C7A7")
                .encode(
                    x=alt.X("Mes:N", title="Mes"),
                    y=alt.Y(f"{estoque_col}:Q", title="Estoque"),
                    tooltip=["Mes", alt.Tooltip(f"{estoque_col}:Q", format=",.0f")],
                )
            )
            line = (
                alt.Chart(monthly)
                .mark_line(color="#1f4e7a", point=True)
                .encode(
                    x=alt.X("Mes:N", title="Mes"),
                    y=alt.Y(f"{vendas_col}:Q", title="Vendas liquidas"),
                    tooltip=["Mes", alt.Tooltip(f"{vendas_col}:Q", format=",.0f")],
                )
            )
            st.altair_chart((bar + line).properties(height=320), width="stretch")

st.subheader("Reajuste por índice (agregado pelos filtros)")
st.caption(
    "Cada ponto usa o VGV Oferta Final do próprio mês. "
    "Use o seletor para exibir somente as linhas de índices desejadas."
)

if reajuste_error:
    st.info(reajuste_error)
elif filtered_reajuste.empty:
    st.info("Sem dados de reajuste para os filtros atuais.")
else:
    corrected_columns = [
        f"VGV Corrigido {index_name}"
        for index_name in REAJUSTE_INDEX_ORDER
        if f"VGV Corrigido {index_name}" in filtered_reajuste.columns
    ]
    agg_map: dict[str, str] = {"VGV Nominal": "sum"}
    for corrected_col in corrected_columns:
        agg_map[corrected_col] = "sum"

    reajuste_monthly = (
        filtered_reajuste.groupby(["Mes", "MesData"], as_index=False)
        .agg(agg_map)
        .sort_values("MesData")
    )

    if reajuste_monthly.empty:
        st.info("Sem dados de reajuste para os filtros atuais.")
    else:
        reference_row = reajuste_monthly.iloc[-1]
        reference_month_label = str(reference_row.get("Mes", "-"))
        start_month_label = str(reajuste_monthly.iloc[0].get("Mes", "-"))

        target_label = (
            filtered_empreendimentos[0]
            if len(filtered_empreendimentos) == 1
            else f"{len(filtered_empreendimentos)} (filtros)"
        )

        available_index_options = []
        for index_name in REAJUSTE_INDEX_ORDER:
            corrected_col = f"VGV Corrigido {index_name}"
            if corrected_col not in reajuste_monthly.columns:
                continue
            has_values = pd.to_numeric(reajuste_monthly[corrected_col], errors="coerce").notna().any()
            if has_values:
                available_index_options.append(index_name)

        default_selected_indices = ["INCC-DI"] if "INCC-DI" in available_index_options else available_index_options[:1]
        current_selected_indices = st.session_state.get(REAJUSTE_INDEX_WIDGET_KEY, [])
        if not isinstance(current_selected_indices, list):
            current_selected_indices = []
        current_selected_indices = [name for name in current_selected_indices if name in available_index_options]
        if not current_selected_indices:
            current_selected_indices = default_selected_indices
        st.session_state[REAJUSTE_INDEX_WIDGET_KEY] = current_selected_indices

        if available_index_options:
            st.multiselect(
                "Linhas de reajuste por índice",
                options=available_index_options,
                key=REAJUSTE_INDEX_WIDGET_KEY,
            )
        else:
            st.info("Nenhum índice disponível para exibição no recorte atual.")

        selected_indices = [name for name in st.session_state.get(REAJUSTE_INDEX_WIDGET_KEY, []) if name in available_index_options]
        metric_label_map = {
            "INCC-DI": "Corrigido INCC-DI (mês ref)",
            "IPCA": "Corrigido IPCA (mês ref)",
            "IGP-DI": "Corrigido IGP-DI (mês ref)",
        }

        metric_columns = st.columns(2 + len(selected_indices))
        metric_columns[0].metric("Empreendimento", target_label)
        metric_columns[1].metric("Nominal (mês ref)", _format_brl_compact(reference_row.get("VGV Nominal")))
        for idx, index_name in enumerate(selected_indices):
            metric_columns[idx + 2].metric(
                metric_label_map.get(index_name, f"Corrigido {index_name} (mês ref)"),
                _format_brl_compact(reference_row.get(f"VGV Corrigido {index_name}")),
            )

        base_dates = reajuste_meta.get("base_dates", {})
        base_labels = []
        for index_name in selected_indices:
            base_date = base_dates.get(index_name)
            if isinstance(base_date, pd.Timestamp):
                base_labels.append(f"{index_name}: {base_date.strftime('%m/%Y')}")

        caption_text = f"Série exibida: {start_month_label} até {reference_month_label}"
        if base_labels:
            caption_text += " | Base usada: " + " | ".join(base_labels)
        st.caption(caption_text)

        missing_indices = [
            index_name
            for index_name in reajuste_meta.get("missing_indices", [])
            if index_name in REAJUSTE_INDEX_ORDER
        ]
        if missing_indices:
            st.caption("Índices indisponíveis no assets: " + ", ".join(missing_indices))

        with st.expander("Resumo metodológico do reajuste", expanded=False):
            st.markdown(
                "\n".join(
                    [
                        "**Métricas exibidas**",
                        "- Empreendimento: 1 nome selecionado ou N (filtros).",
                        "- Nominal (mês ref): soma do VGV Oferta Final no último mês da série exibida.",
                        "- Corrigidos (mês ref): nominais atualizados para base 12/2025 conforme índices selecionados.",
                        "",
                        "**Índices disponíveis**",
                        "- O seletor permite mostrar/ocultar INCC-DI, IPCA e IGP-DI.",
                        "- Por padrão, o gráfico inicia com INCC-DI selecionado.",
                        "",
                        "**Cálculo aplicado**",
                        "- Método por índice direto: VGV_corrigido = VGV_nominal * (Indice_base / Indice_mes).",
                        "- O mesmo método é aplicado para cada índice disponível no assets.",
                    ]
                )
            )

        selected_value_vars = [
            f"VGV Corrigido {index_name}"
            for index_name in selected_indices
            if f"VGV Corrigido {index_name}" in reajuste_monthly.columns
        ]
        series_labels = {"VGV Nominal": "VGV Oferta Final (nominal)"}
        for index_name in selected_indices:
            series_labels[f"VGV Corrigido {index_name}"] = f"VGV corrigido ({index_name})"

        reajuste_plot = reajuste_monthly.melt(
            id_vars=["Mes", "MesData"],
            value_vars=["VGV Nominal"] + selected_value_vars,
            var_name="Serie",
            value_name="Valor",
        )
        reajuste_plot["Valor"] = pd.to_numeric(reajuste_plot["Valor"], errors="coerce")
        reajuste_plot = reajuste_plot.dropna(subset=["Valor"])
        reajuste_plot["Serie"] = reajuste_plot["Serie"].astype(str).replace(series_labels)

        reajuste_chart = (
            alt.Chart(reajuste_plot)
            .mark_line(point=True)
            .encode(
                x=alt.X("MesData:T", title="Mês"),
                y=alt.Y("Valor:Q", title="VGV (R$)"),
                color=alt.Color("Serie:N", title="Serie"),
                tooltip=["Mes", "Serie", alt.Tooltip("Valor:Q", format=",.2f")],
            )
            .properties(height=320)
        )
        st.altair_chart(reajuste_chart, width="stretch")

# Ficha + amenidades apenas quando houver 1 empreendimento no filtro
if len(filtered_empreendimentos) != 1:
    st.info(
        "Ficha do empreendimento e amenidades ficam disponíveis quando o filtro retorna um único empreendimento. "
        "Dica: clique em um ponto no mapa para aplicar esse filtro automaticamente."
    )
else:
    selected_empreendimento = filtered_empreendimentos[0]
    st.session_state["selected_empreendimento"] = selected_empreendimento

    selected_rows = filtered_base[filtered_base[empreendimento_col].astype(str) == selected_empreendimento].copy()
    if selected_rows.empty:
        st.info("Não foi possível montar detalhes para o empreendimento selecionado.")
    else:
        row_for_details = selected_rows.sort_values(by=tipologia_col).iloc[0] if tipologia_col else selected_rows.iloc[0]
        all_columns = list(base_df.columns)

        with st.expander("Ficha do empreendimento", expanded=False):
            ficha_fields = [
                "Empreendimento",
                "Endereço",
                "Número",
                "Bairro",
                "CEP",
                "Cidade",
                "Estado",
                "Latitude",
                "Longitude",
                "Incorporadora 1",
                "Incorporadora 2",
                "Incorporadora 3",
                "Data de Lançamento",
                "Data de Entrega",
                "Tipo",
                "Quartos",
                "Garagem",
                "Torres",
                "Elevadores",
                "Unidades por Tipologia",
                "M2 Privativo",
                "Padrão",
                "Tipologia",
                "Oferta Lançada",
            ]

            ficha_data: list[dict[str, Any]] = []
            for field in ficha_fields:
                original_col = _find_column(all_columns, [field])
                if not original_col:
                    continue

                value = row_for_details.get(original_col)
                if "data" in normalize_text(field):
                    if pd.notna(value):
                        value = pd.to_datetime(value, errors="coerce")
                        value = value.strftime("%d/%m/%Y") if pd.notna(value) else "-"
                    else:
                        value = "-"
                elif isinstance(value, float) and pd.isna(value):
                    value = "-"

                ficha_data.append({"Campo": field, "Valor": value})

            if ficha_data:
                ficha_df = pd.DataFrame(ficha_data)
                if "Valor" in ficha_df.columns:
                    ficha_df["Valor"] = ficha_df["Valor"].map(_display_value_text)
                st.dataframe(ficha_df, width="stretch", hide_index=True)
            else:
                st.info("Não foi possível montar a ficha com as colunas esperadas.")

        with st.expander("Amenidades presentes (Sim)", expanded=False):
            if not amenity_columns:
                st.info("Não foi possível detectar colunas de amenidades automaticamente.")
            else:
                merged_groups = {"Interna": set(), "Externa": set(), "Comercial": set(), "Geral": set()}
                for _, row in selected_rows.iterrows():
                    row_groups = extract_present_amenities(row, amenity_columns)
                    for group_name, values in row_groups.items():
                        merged_groups.setdefault(group_name, set()).update(values)

                amenity_groups = {
                    group_name: sorted(values, key=normalize_text)
                    for group_name, values in merged_groups.items()
                }
                total_present = sum(len(values) for values in amenity_groups.values())

                if total_present == 0:
                    st.info("Nenhuma amenidade marcada como 'Sim' para o empreendimento filtrado.")
                else:
                    g1, g2, g3, g4 = st.columns(4)
                    col_map = {
                        "Interna": g1,
                        "Externa": g2,
                        "Comercial": g3,
                        "Geral": g4,
                    }

                    for group_name in ("Interna", "Externa", "Comercial", "Geral"):
                        values = amenity_groups.get(group_name, [])
                        with col_map[group_name]:
                            st.markdown(f"**{group_name} ({len(values)})**")
                            if not values:
                                st.caption("-")
                            else:
                                st.markdown("\n".join(f"- {item}" for item in values))


st.subheader("Exportar dados")
st.caption(
    "Escolha entre exportar todos os empreendimentos da base carregada ou somente o recorte atual dos filtros."
)

all_export_sheets = {
    "Empreendimentos": base_enriched,
    "Performance_Mensal": perf_df,
    "Reajuste_INCC": reajuste_perf,
}
filtered_export_sheets = {
    "Empreendimentos": filtered_base,
    "Performance_Mensal": filtered_perf,
    "Reajuste_INCC": filtered_reajuste,
}

all_bytes = _to_excel_bytes(all_export_sheets)
filtered_bytes = _to_excel_bytes(filtered_export_sheets)

export_col1, export_col2 = st.columns(2)
export_col1.download_button(
    "Exportar: todos os empreendimentos",
    data=all_bytes,
    file_name="dados_vgv_todos_empreendimentos.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    width="stretch",
)
export_col2.download_button(
    "Exportar: aplicar filtros atuais",
    data=filtered_bytes,
    file_name="dados_vgv_filtros_atuais.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    width="stretch",
)

