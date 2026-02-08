from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.theme import apply_brain_theme, render_sidebar_menu
from src.vgv_parser import extract_present_amenities, normalize_text, parse_vgv_workbook

APP_NAME = "Atualizador de VGV"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon=":bar_chart:")
apply_brain_theme()
render_sidebar_menu()


@st.cache_data(show_spinner=False)
def _parse_uploaded(file_bytes: bytes):
    return parse_vgv_workbook(BytesIO(file_bytes))


@st.cache_data(show_spinner=False)
def _parse_sample(path_text: str):
    return parse_vgv_workbook(path_text)


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {normalize_text(col): col for col in columns}

    for candidate in candidates:
        key = normalize_text(candidate)
        if key in normalized:
            return normalized[key]

    for candidate in candidates:
        key = normalize_text(candidate)
        for col in columns:
            col_norm = normalize_text(col)
            if key in col_norm or col_norm in key:
                return col

    return None


def _format_number(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def _format_decimal(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(value)


def _format_brl(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    return "R$ " + _format_decimal(value)


def _selection_index_from_event(event: Any) -> int | None:
    if event is None:
        return None

    candidate = event
    if isinstance(candidate, dict):
        candidate = candidate.get("selection", candidate)
        if isinstance(candidate, dict):
            for key in ("indices", "rows", "objects", "points"):
                values = candidate.get(key)
                if isinstance(values, list) and values:
                    first = values[0]
                    if isinstance(first, int):
                        return first
                    if isinstance(first, dict):
                        for nested_key in ("index", "row", "id"):
                            nested_value = first.get(nested_key)
                            if isinstance(nested_value, int):
                                return nested_value

    selection = getattr(event, "selection", None)
    if selection is not None:
        for key in ("indices", "rows"):
            values = getattr(selection, key, None)
            if isinstance(values, list) and values:
                first = values[0]
                if isinstance(first, int):
                    return first

    return None


def _clean_options(series: pd.Series) -> list[str]:
    values = [str(v) for v in series.dropna().astype(str).tolist() if str(v).strip()]
    return sorted(set(values))


def _status_color(status_value: Any) -> list[int]:
    status_norm = normalize_text(status_value)
    if "esgotado" in status_norm:
        return [176, 0, 32, 180]
    if "ativo" in status_norm:
        return [91, 117, 55, 180]
    return [31, 78, 122, 170]


def _map_style_light() -> str:
    styles = getattr(pdk, "map_styles", None)
    if styles is not None and hasattr(styles, "LIGHT"):
        return getattr(styles, "LIGHT")
    return "light"


st.title(APP_NAME)
st.caption("Mapa, series mensais, ficha do empreendimento e amenidades em uma unica pagina.")

sample_path = Path(__file__).resolve().parent / "assets" / "tabelaEmpreendimentoReduzida.xlsx"

with st.expander("Fonte de dados", expanded=True):
    uploaded_file = st.file_uploader("Planilha no formato padrao", type=["xlsx", "xls"])
    b1, b2, _ = st.columns([1, 1, 2])
    use_sample = b1.button(
        "Usar exemplo de assets",
        use_container_width=True,
        disabled=not sample_path.exists(),
    )
    clear_source = b2.button("Limpar", use_container_width=True)

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
            "selected_empreendimento",
            "filter_empreendimentos",
            "filter_cidades",
            "filter_tipologias",
            "filter_status",
        ):
            st.session_state.pop(key, None)

if "source_mode" not in st.session_state and sample_path.exists():
    st.session_state["source_mode"] = "sample"
    st.session_state["source_name"] = sample_path.name

source_mode = st.session_state.get("source_mode")
base_df: pd.DataFrame | None = None
perf_df: pd.DataFrame | None = None
metadata: dict[str, Any] | None = None

try:
    if source_mode == "upload" and st.session_state.get("source_bytes"):
        base_df, perf_df, metadata = _parse_uploaded(st.session_state["source_bytes"])
    elif source_mode == "sample" and sample_path.exists():
        base_df, perf_df, metadata = _parse_sample(str(sample_path))
except Exception as exc:
    st.error(f"Falha ao ler planilha: {exc}")
    st.stop()

if base_df is None or perf_df is None or metadata is None:
    st.info("Carregue uma planilha para iniciar a analise.")
    st.stop()

if base_df.empty:
    st.warning("A planilha nao possui linhas de dados apos a limpeza inicial.")
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
    st.error("A coluna 'Empreendimento' e obrigatoria para a analise.")
    st.stop()

status_metric_col = _find_column(list(perf_df.columns), ["Status"])
vgv_total_col = _find_column(list(perf_df.columns), ["VGV Total"])
vgv_oferta_col = _find_column(list(perf_df.columns), ["VGV Oferta Final"])
estoque_col = _find_column(list(perf_df.columns), ["Estoque"])
vendas_col = _find_column(list(perf_df.columns), ["Vendas"])
preco_col = _find_column(list(perf_df.columns), ["Preco"])
preco_lanc_col = _find_column(list(perf_df.columns), ["Preco de Lancamento", "Preco de Lan?amento"])

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

FILTER_EMP_KEY = "filter_empreendimentos"
FILTER_CITY_KEY = "filter_cidades"
FILTER_TIPO_KEY = "filter_tipologias"
FILTER_STATUS_KEY = "filter_status"

for key in (FILTER_EMP_KEY, FILTER_CITY_KEY, FILTER_TIPO_KEY, FILTER_STATUS_KEY):
    st.session_state.setdefault(key, [])


st.subheader("Filtros")
st.caption("Sem selecao em um filtro = todos os registros daquele campo.")

empreendimento_options = _clean_options(base_enriched[empreendimento_col])
city_options = _clean_options(base_enriched[cidade_col]) if cidade_col else []
tip_options = _clean_options(base_enriched[tipologia_col]) if tipologia_col else []
status_options = (
    _clean_options(base_enriched["Status Atual"]) if "Status Atual" in base_enriched.columns else []
)


def _sanitize_filter_state(key: str, options: list[str]) -> None:
    current = st.session_state.get(key, []) or []
    st.session_state[key] = [value for value in current if value in options]


_sanitize_filter_state(FILTER_EMP_KEY, empreendimento_options)
_sanitize_filter_state(FILTER_CITY_KEY, city_options)
_sanitize_filter_state(FILTER_TIPO_KEY, tip_options)
_sanitize_filter_state(FILTER_STATUS_KEY, status_options)

fc1, fc2, fc3, fc4 = st.columns(4)
fc1.multiselect("Empreendimento", options=empreendimento_options, key=FILTER_EMP_KEY)
fc2.multiselect("Cidade", options=city_options, key=FILTER_CITY_KEY)
fc3.multiselect("Tipologia", options=tip_options, key=FILTER_TIPO_KEY)
fc4.multiselect("Status atual", options=status_options, key=FILTER_STATUS_KEY)

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
    st.warning("Nao ha coordenadas validas para exibir o mapa com os filtros atuais.")
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
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-object",
            key="empreendimento_map",
        )
    except TypeError:
        st.pydeck_chart(deck, use_container_width=True, key="empreendimento_map_static")

    point_options = points["Empreendimento"].astype(str).tolist()

    if len(st.session_state[FILTER_EMP_KEY]) == 1 and st.session_state[FILTER_EMP_KEY][0] in point_options:
        st.session_state["selected_empreendimento"] = st.session_state[FILTER_EMP_KEY][0]
    elif st.session_state.get("selected_empreendimento") not in point_options:
        st.session_state["selected_empreendimento"] = point_options[0]

    selected_index = _selection_index_from_event(map_event)
    if selected_index is not None and 0 <= selected_index < len(points):
        clicked_empreendimento = str(points.iloc[selected_index]["Empreendimento"])
        needs_filter_update = (
            st.session_state[FILTER_EMP_KEY] != [clicked_empreendimento]
            or bool(st.session_state[FILTER_CITY_KEY])
            or bool(st.session_state[FILTER_TIPO_KEY])
            or bool(st.session_state[FILTER_STATUS_KEY])
        )
        st.session_state["selected_empreendimento"] = clicked_empreendimento

        if needs_filter_update:
            st.session_state[FILTER_EMP_KEY] = [clicked_empreendimento]
            st.session_state[FILTER_CITY_KEY] = []
            st.session_state[FILTER_TIPO_KEY] = []
            st.session_state[FILTER_STATUS_KEY] = []
            st.rerun()

    if st.session_state.get("selected_empreendimento"):
        st.caption(f"Empreendimento em foco no mapa: {st.session_state['selected_empreendimento']}")

# Graficos temporais (sempre usando todos os meses disponiveis no arquivo)
st.subheader("Series mensais de VGV (agregado pelos filtros)")

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
        k1.metric("Mes de referencia", str(last_row.get("Mes", "-")))
        if vgv_total_col and vgv_total_col in monthly.columns:
            k2.metric("VGV Total", _format_brl(last_row.get(vgv_total_col)))
        if vgv_oferta_col and vgv_oferta_col in monthly.columns:
            k3.metric("VGV Oferta Final", _format_brl(last_row.get(vgv_oferta_col)))
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
            st.altair_chart(vgv_chart, use_container_width=True)

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
            st.altair_chart((bar + line).properties(height=320), use_container_width=True)

# Ficha + amenidades apenas quando houver 1 empreendimento no filtro
if len(filtered_empreendimentos) != 1:
    st.info(
        "Ficha do empreendimento e amenidades ficam disponiveis quando o filtro retorna um unico empreendimento. "
        "Dica: clique em um ponto no mapa para aplicar esse filtro automaticamente."
    )
    st.stop()

selected_empreendimento = filtered_empreendimentos[0]
st.session_state["selected_empreendimento"] = selected_empreendimento

selected_rows = filtered_base[filtered_base[empreendimento_col].astype(str) == selected_empreendimento].copy()
if selected_rows.empty:
    st.info("Nao foi possivel montar detalhes para o empreendimento selecionado.")
    st.stop()

row_for_details = selected_rows.sort_values(by=tipologia_col).iloc[0] if tipologia_col else selected_rows.iloc[0]
all_columns = list(base_df.columns)

with st.expander("Ficha do empreendimento", expanded=False):
    ficha_fields = [
        "Empreendimento",
        "Endereco",
        "Numero",
        "Bairro",
        "CEP",
        "Cidade",
        "Estado",
        "Latitude",
        "Longitude",
        "Incorporadora 1",
        "Incorporadora 2",
        "Incorporadora 3",
        "Data de Lancamento",
        "Data de Entrega",
        "Tipo",
        "Quartos",
        "Garagem",
        "Torres",
        "Elevadores",
        "Unidades por Tipologia",
        "M2 Privativo",
        "Padrao",
        "Tipologia",
        "Oferta Lancada",
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
        st.dataframe(pd.DataFrame(ficha_data), use_container_width=True, hide_index=True)
    else:
        st.info("Nao foi possivel montar a ficha com as colunas esperadas.")

with st.expander("Amenidades presentes (Sim)", expanded=False):
    if not amenity_columns:
        st.info("Nao foi possivel detectar colunas de amenidades automaticamente.")
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
