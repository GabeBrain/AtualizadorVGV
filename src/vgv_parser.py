from __future__ import annotations

import re
import unicodedata
from io import BytesIO
from typing import Any

import pandas as pd

MONTH_TOKEN_RE = re.compile(r"^(0[1-9]|1[0-2])/\d{4}$")
MONTH_SUFFIX_RE = re.compile(r"^(?P<metric>.+?)\s(?P<month>(0[1-9]|1[0-2])/\d{4})$")

DEFAULT_BLOCK_METRICS = [
    "Estoque",
    "Vendas",
    "Preco",
    "VGV Total",
    "VGV Oferta Final",
    "Status",
    "Preco de Lancamento",
]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def _read_raw_excel(source: Any) -> pd.DataFrame:
    df = pd.read_excel(source, sheet_name=0)
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df.columns = [str(col).strip() for col in df.columns]
    return df.reset_index(drop=True)


def _month_start_indexes(columns: list[str]) -> list[int]:
    idx_list: list[int] = []
    for idx, col in enumerate(columns):
        if MONTH_TOKEN_RE.match(str(col).strip()):
            idx_list.append(idx)
    return idx_list


def _unique_name(name: str, used: set[str]) -> str:
    candidate = name
    counter = 2
    while candidate in used:
        candidate = f"{name} ({counter})"
        counter += 1
    used.add(candidate)
    return candidate


def _rename_monthly_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    columns = list(df.columns)
    starts = _month_start_indexes(columns)
    if not starts:
        return df, {}, []

    rename_map: dict[str, str] = {}
    used = set(str(col) for col in columns)

    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(columns)
        block = columns[start:end]
        month_token = str(columns[start]).strip()

        for offset, col in enumerate(block):
            header_value = df.iloc[0, df.columns.get_loc(col)]
            header_text = str(header_value).strip() if pd.notna(header_value) else ""

            if header_text:
                candidate = header_text
            else:
                metric = DEFAULT_BLOCK_METRICS[offset] if offset < len(DEFAULT_BLOCK_METRICS) else f"Metrica {offset + 1}"
                candidate = metric if month_token in metric else f"{metric} {month_token}"

            unique = _unique_name(candidate, used)
            rename_map[col] = unique

    renamed = df.rename(columns=rename_map)
    month_cols = [name for name in rename_map.values() if MONTH_SUFFIX_RE.match(str(name))]
    return renamed, rename_map, month_cols


def _looks_like_header_row(df: pd.DataFrame, month_metric_cols: list[str]) -> bool:
    if df.empty or not month_metric_cols:
        return False

    first_row = df.iloc[0]
    score = 0
    tokens = ("estoque", "vendas", "vgv", "preco", "status", "lanc", "oferta")

    for col in month_metric_cols:
        value = first_row.get(col)
        if pd.isna(value):
            continue
        text = normalize_text(value)
        if re.search(r"(0[1-9]|1[0-2])/\d{4}", text) or any(token in text for token in tokens):
            score += 1

    threshold = max(3, int(len(month_metric_cols) * 0.25))
    return score >= threshold


def _month_metric_map(columns: list[str]) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for col in columns:
        match = MONTH_SUFFIX_RE.match(str(col).strip())
        if not match:
            continue
        metric = str(match.group("metric")).strip()
        month = str(match.group("month")).strip()
        mapping.setdefault(month, {})[metric] = col
    return mapping


def _sort_month_labels(labels: list[str]) -> list[str]:
    return sorted(
        labels,
        key=lambda label: pd.to_datetime(f"01/{label}", format="%d/%m/%Y", errors="coerce"),
    )


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _build_performance_long(base_df: pd.DataFrame, month_map: dict[str, dict[str, str]]) -> pd.DataFrame:
    if not month_map:
        return pd.DataFrame(columns=["__registro_id", "Empreendimento", "Tipologia", "Mes", "MesData"])

    records: list[dict[str, Any]] = []
    month_labels = _sort_month_labels(list(month_map.keys()))

    for _, row in base_df.iterrows():
        for month in month_labels:
            metric_cols = month_map.get(month, {})
            rec: dict[str, Any] = {
                "__registro_id": row.get("__registro_id"),
                "Empreendimento": row.get("Empreendimento"),
                "Tipologia": row.get("Tipologia"),
                "Mes": month,
            }
            for metric_name, col_name in metric_cols.items():
                rec[metric_name] = row.get(col_name)
            records.append(rec)

    perf = pd.DataFrame(records)
    perf["MesData"] = pd.to_datetime(
        "01/" + perf["Mes"].astype(str), format="%d/%m/%Y", errors="coerce"
    )

    protected = {"__registro_id", "Empreendimento", "Tipologia", "Mes", "MesData"}
    for col in perf.columns:
        if col in protected:
            continue
        if "status" in normalize_text(col):
            perf[col] = perf[col].astype("string")
        else:
            perf[col] = _to_numeric(perf[col])

    perf = perf.sort_values(["MesData", "Empreendimento", "Tipologia"], ascending=[True, True, True])
    return perf.reset_index(drop=True)


def _is_yes(value: Any) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) > 0

    text = normalize_text(value)
    return text in {"sim", "s", "yes", "true", "1", "x"}


def identify_amenity_columns(base_df: pd.DataFrame, month_map: dict[str, dict[str, str]] | None = None) -> list[str]:
    month_cols: set[str] = set()
    if month_map:
        for cols in month_map.values():
            month_cols.update(cols.values())

    blocked_keywords = (
        "endereco",
        "bairro",
        "cidade",
        "estado",
        "latitude",
        "longitude",
        "incorporadora",
        "data",
        "quartos",
        "garagem",
        "torres",
        "elevadores",
        "tipologia",
        "padrao",
        "oferta",
        "financiamento",
        "alienacao",
        "retrofit",
        "tempo de venda",
        "id",
        "cep",
        "numero",
        "tipo",
    )

    amenity_cols: list[str] = []
    for col in base_df.columns:
        if col.startswith("__") or col in month_cols:
            continue

        low_name = normalize_text(col)
        has_suffix = (
            " - interna" in low_name
            or " - externa" in low_name
            or " - comercial" in low_name
        )
        has_tem_prefix = low_name.startswith("tem ")

        if has_suffix or has_tem_prefix:
            amenity_cols.append(col)
            continue

        values = base_df[col].dropna()
        if values.empty:
            continue

        normalized = values.astype(str).map(normalize_text)
        bool_ratio = normalized.isin({"sim", "nao", "0", "1", "true", "false", "yes", "no"}).mean()
        if bool_ratio >= 0.85 and not any(word in low_name for word in blocked_keywords):
            amenity_cols.append(col)

    return amenity_cols


def extract_present_amenities(row: pd.Series, amenity_columns: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {"Interna": [], "Externa": [], "Comercial": [], "Geral": []}

    for col in amenity_columns:
        if not _is_yes(row.get(col)):
            continue

        label = str(col)
        group = "Geral"
        normalized_name = normalize_text(col)

        if " - interna" in normalized_name:
            group = "Interna"
            label = str(col).rsplit(" - ", 1)[0]
        elif " - externa" in normalized_name:
            group = "Externa"
            label = str(col).rsplit(" - ", 1)[0]
        elif " - comercial" in normalized_name:
            group = "Comercial"
            label = str(col).rsplit(" - ", 1)[0]
        elif normalized_name.startswith("tem "):
            label = str(col)[4:]

        groups[group].append(label)

    cleaned: dict[str, list[str]] = {}
    for group, labels in groups.items():
        uniq_sorted = sorted(set(labels), key=lambda item: normalize_text(item))
        cleaned[group] = uniq_sorted

    return cleaned


def parse_vgv_workbook(source: Any) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if isinstance(source, (bytes, bytearray)):
        source = BytesIO(source)

    raw = _read_raw_excel(source)
    renamed, rename_map, month_metric_cols = _rename_monthly_columns(raw)

    if _looks_like_header_row(renamed, month_metric_cols):
        renamed = renamed.iloc[1:].reset_index(drop=True)

    renamed["__registro_id"] = range(1, len(renamed) + 1)

    month_map = _month_metric_map(list(renamed.columns))
    month_labels = _sort_month_labels(list(month_map.keys()))

    perf = _build_performance_long(renamed, month_map)
    amenity_cols = identify_amenity_columns(renamed, month_map)

    metadata = {
        "month_labels": month_labels,
        "month_block_count": len(month_labels),
        "month_columns": sorted({col for cols in month_map.values() for col in cols.values()}),
        "amenity_columns": amenity_cols,
        "rename_map": rename_map,
    }

    return renamed, perf, metadata
