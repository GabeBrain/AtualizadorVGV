from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from src.theme import apply_brain_theme, render_sidebar_menu
from src.vgv_parser import normalize_text, parse_vgv_workbook

APP_NAME = "Atualizador de VGV"
TARGET_MONTH_LABELS = ["01/2021", "02/2021", "03/2021"]
PRESENT_BASE_DATE = pd.Timestamp("2025-12-01")
REAJUSTE_EMP_KEY = "reajuste_empreendimento"

st.set_page_config(page_title="Reajuste INCC", layout="wide", page_icon=":chart_with_upwards_trend:")
apply_brain_theme()
render_sidebar_menu()


@st.cache_data(show_spinner=False)
def _parse_uploaded(file_bytes: bytes):
    return parse_vgv_workbook(BytesIO(file_bytes))


@st.cache_data(show_spinner=False)
def _parse_sample(path_text: str):
    return parse_vgv_workbook(path_text)


@st.cache_data(show_spinner=False)
def _load_incc_series(path_text: str) -> pd.DataFrame:
    def _read_sheet(sheet_name: str) -> pd.DataFrame:
        raw = pd.read_excel(path_text, sheet_name=sheet_name, header=1)
        if raw.empty or raw.shape[1] < 2:
            return pd.DataFrame(columns=["MesData", sheet_name])

        date_col = raw.columns[0]
        index_col = raw.columns[1]

        frame = raw[[date_col, index_col]].rename(columns={date_col: "MesData", index_col: sheet_name}).copy()
        frame["MesData"] = pd.to_datetime(frame["MesData"], errors="coerce").dt.to_period("M").dt.to_timestamp()
        frame[sheet_name] = pd.to_numeric(frame[sheet_name], errors="coerce")
        frame = frame.dropna(subset=["MesData", sheet_name]).sort_values("MesData")
        return frame.reset_index(drop=True)

    di = _read_sheet("INCC-DI")
    m = _read_sheet("INCC-M")

    merged = pd.merge(di, m, on="MesData", how="outer")
    merged = merged.sort_values("MesData").drop_duplicates(subset=["MesData"], keep="last")
    return merged.reset_index(drop=True)


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


def _resolve_base_index(index_df: pd.DataFrame, column: str, target_date: pd.Timestamp) -> tuple[float | None, pd.Timestamp | None]:
    if column not in index_df.columns or "MesData" not in index_df.columns:
        return None, None

    frame = index_df[["MesData", column]].copy()
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["MesData", column]).sort_values("MesData")
    if frame.empty:
        return None, None

    exact = frame[frame["MesData"] == target_date]
    if not exact.empty:
        row = exact.iloc[-1]
        return float(row[column]), pd.Timestamp(row["MesData"])

    previous = frame[frame["MesData"] <= target_date]
    if not previous.empty:
        row = previous.iloc[-1]
        return float(row[column]), pd.Timestamp(row["MesData"])

    row = frame.iloc[-1]
    return float(row[column]), pd.Timestamp(row["MesData"])


st.title("Reajuste de VGV a valor presente")
st.caption("Atualizacao do VGV Oferta Final para 12/2025 com INCC-DI e INCC-M.")

nav_col, _ = st.columns([1, 4])
with nav_col:
    if st.button("Voltar para analise principal", use_container_width=True):
        st.switch_page("app.py")

sample_path = Path(__file__).resolve().parents[1] / "assets" / "tabelaEmpreendimentoReduzida.xlsx"
source_mode = st.session_state.get("source_mode")

if source_mode is None and sample_path.exists():
    st.session_state["source_mode"] = "sample"
    st.session_state["source_name"] = sample_path.name
    source_mode = "sample"

base_df: pd.DataFrame | None = None
perf_df: pd.DataFrame | None = None
metadata: dict[str, Any] | None = None

try:
    if source_mode == "upload" and st.session_state.get("source_bytes"):
        base_df, perf_df, metadata = _parse_uploaded(st.session_state["source_bytes"])
    elif source_mode == "sample" and sample_path.exists():
        base_df, perf_df, metadata = _parse_sample(str(sample_path))
except Exception as exc:
    st.error(f"Falha ao ler planilha principal: {exc}")
    st.stop()

if base_df is None or perf_df is None or metadata is None:
    st.info("Abra primeiro a pagina principal e carregue uma planilha para habilitar o reajuste.")
    st.stop()

empreendimento_col = _find_column(list(perf_df.columns), ["Empreendimento"])
vgv_oferta_col = _find_column(list(perf_df.columns), ["VGV Oferta Final"])

if not empreendimento_col or not vgv_oferta_col:
    st.error("Nao foi possivel encontrar as colunas de Empreendimento e VGV Oferta Final na planilha.")
    st.stop()

if "MesData" not in perf_df.columns:
    if "Mes" in perf_df.columns:
        perf_df["MesData"] = pd.to_datetime("01/" + perf_df["Mes"].astype(str), format="%d/%m/%Y", errors="coerce")
    else:
        st.error("Nao foi possivel identificar a data mensal para o reajuste.")
        st.stop()

if "Mes" not in perf_df.columns:
    perf_df["Mes"] = perf_df["MesData"].dt.strftime("%m/%Y")

empreendimento_options = sorted(set(perf_df[empreendimento_col].dropna().astype(str).tolist()))
if not empreendimento_options:
    st.warning("Nao ha empreendimentos disponiveis para analise.")
    st.stop()

preferred_emp = st.session_state.get(REAJUSTE_EMP_KEY) or st.session_state.get("selected_empreendimento")
default_index = empreendimento_options.index(preferred_emp) if preferred_emp in empreendimento_options else 0

selected_empreendimento = st.selectbox(
    "Empreendimento",
    options=empreendimento_options,
    index=default_index,
)
st.session_state[REAJUSTE_EMP_KEY] = selected_empreendimento
st.session_state["selected_empreendimento"] = selected_empreendimento

series_mode = st.radio(
    "Serie para comparacao no grafico",
    options=["Comparar ambos", "INCC-DI", "INCC-M"],
    horizontal=True,
)

perf_emp = perf_df.copy()
perf_emp[empreendimento_col] = perf_emp[empreendimento_col].astype(str)
perf_emp = perf_emp[perf_emp[empreendimento_col] == selected_empreendimento].copy()
perf_emp[vgv_oferta_col] = pd.to_numeric(perf_emp[vgv_oferta_col], errors="coerce")
perf_emp = perf_emp.dropna(subset=["MesData", vgv_oferta_col])

analysis_df = perf_emp[perf_emp["Mes"].isin(TARGET_MONTH_LABELS)].copy()
if analysis_df.empty:
    st.warning(
        "Nao ha dados para os meses 01/2021, 02/2021 e 03/2021 no empreendimento selecionado."
    )
    st.stop()

monthly = (
    analysis_df.groupby(["Mes", "MesData"], as_index=False)[vgv_oferta_col]
    .sum()
    .sort_values("MesData")
)
monthly = monthly.rename(columns={vgv_oferta_col: "VGV Nominal"})

incc_path = Path(__file__).resolve().parents[1] / "assets" / "INCC_Series_MeDI.xlsx"
if not incc_path.exists():
    st.error("Arquivo INCC_Series_MeDI.xlsx nao encontrado em assets/.")
    st.stop()

try:
    incc_df = _load_incc_series(str(incc_path))
except Exception as exc:
    st.error(f"Falha ao ler arquivo de indices INCC: {exc}")
    st.stop()

if incc_df.empty:
    st.error("Arquivo de INCC sem dados validos.")
    st.stop()

base_di, base_di_date = _resolve_base_index(incc_df, "INCC-DI", PRESENT_BASE_DATE)
base_m, base_m_date = _resolve_base_index(incc_df, "INCC-M", PRESENT_BASE_DATE)

if base_di is None and base_m is None:
    st.error("Nao foi possivel encontrar valores de base do INCC para a data alvo.")
    st.stop()

monthly = monthly.merge(incc_df, on="MesData", how="left")

if base_di is not None and "INCC-DI" in monthly.columns:
    monthly["VGV Corrigido INCC-DI"] = monthly["VGV Nominal"] * base_di / monthly["INCC-DI"].replace(0, pd.NA)
else:
    monthly["VGV Corrigido INCC-DI"] = pd.NA

if base_m is not None and "INCC-M" in monthly.columns:
    monthly["VGV Corrigido INCC-M"] = monthly["VGV Nominal"] * base_m / monthly["INCC-M"].replace(0, pd.NA)
else:
    monthly["VGV Corrigido INCC-M"] = pd.NA

missing_months = [month for month in TARGET_MONTH_LABELS if month not in set(monthly["Mes"].tolist())]
if missing_months:
    st.warning("Meses sem dados no empreendimento: " + ", ".join(missing_months))

if base_di_date is not None and base_di_date != PRESENT_BASE_DATE:
    st.warning(f"Base INCC-DI usada: {base_di_date.strftime('%m/%Y')} (12/2025 nao encontrado)")
if base_m_date is not None and base_m_date != PRESENT_BASE_DATE:
    st.warning(f"Base INCC-M usada: {base_m_date.strftime('%m/%Y')} (12/2025 nao encontrado)")

with st.expander("Logica aplicada no calculo", expanded=False):
    st.markdown(
        "\n".join(
            [
                "1. Parte do VGV Oferta Final mensal de cada linha e soma por mes.",
                "2. Filtra os meses de 01/2021, 02/2021 e 03/2021.",
                "3. Corrige para valor presente em 12/2025 com formula:",
                "   VGV_corrigido = VGV_nominal * (Indice_12/2025 / Indice_mes).",
                "4. Permite comparar nominal vs corrigido por INCC-DI e/ou INCC-M.",
            ]
        )
    )

m1, m2, m3, m4 = st.columns(4)
m1.metric("Empreendimento", selected_empreendimento)
m2.metric("Soma nominal", _format_brl(monthly["VGV Nominal"].sum()))
m3.metric("Soma corrigida INCC-DI", _format_brl(monthly["VGV Corrigido INCC-DI"].sum(min_count=1)))
m4.metric("Soma corrigida INCC-M", _format_brl(monthly["VGV Corrigido INCC-M"].sum(min_count=1)))

base_di_label = base_di_date.strftime("%m/%Y") if base_di_date is not None else "-"
base_m_label = base_m_date.strftime("%m/%Y") if base_m_date is not None else "-"
st.caption(
    f"Base alvo: 12/2025 | Base INCC-DI usada: {base_di_label} | Base INCC-M usada: {base_m_label}"
)

plot_columns = ["VGV Nominal"]
label_map = {"VGV Nominal": "VGV Oferta Final (nominal)"}

if series_mode in {"Comparar ambos", "INCC-DI"}:
    plot_columns.append("VGV Corrigido INCC-DI")
    label_map["VGV Corrigido INCC-DI"] = "VGV corrigido (INCC-DI)"

if series_mode in {"Comparar ambos", "INCC-M"}:
    plot_columns.append("VGV Corrigido INCC-M")
    label_map["VGV Corrigido INCC-M"] = "VGV corrigido (INCC-M)"

plot_df = monthly[["Mes", "MesData", *plot_columns]].melt(
    id_vars=["Mes", "MesData"],
    value_vars=plot_columns,
    var_name="Serie",
    value_name="Valor",
)
plot_df = plot_df.dropna(subset=["Valor"])
plot_df["Serie"] = plot_df["Serie"].map(label_map).fillna(plot_df["Serie"])

chart = (
    alt.Chart(plot_df)
    .mark_line(point=True)
    .encode(
        x=alt.X("MesData:T", title="Mes"),
        y=alt.Y("Valor:Q", title="VGV (R$)"),
        color=alt.Color("Serie:N", title="Serie"),
        tooltip=["Mes", "Serie", alt.Tooltip("Valor:Q", format=",.2f")],
    )
    .properties(height=360)
)
st.altair_chart(chart, use_container_width=True)

st.subheader("Tabela de apoio")

display_df = monthly[
    [
        "Mes",
        "VGV Nominal",
        "INCC-DI",
        "VGV Corrigido INCC-DI",
        "INCC-M",
        "VGV Corrigido INCC-M",
    ]
].copy()

for column in ["VGV Nominal", "VGV Corrigido INCC-DI", "VGV Corrigido INCC-M"]:
    display_df[column] = display_df[column].map(_format_brl)

for column in ["INCC-DI", "INCC-M"]:
    display_df[column] = display_df[column].map(_format_decimal)

st.dataframe(display_df, use_container_width=True, hide_index=True)
