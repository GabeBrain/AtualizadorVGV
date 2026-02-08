from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

NONE_OPTION = "(nenhum)"


@dataclass(frozen=True)
class ColumnProfile:
    all_columns: list[str]
    numeric_columns: list[str]
    datetime_columns: list[str]
    categorical_columns: list[str]


def _normalize_column_name(column: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", column.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "coluna"


def _dedupe_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for col in columns:
        index = seen.get(col, 0)
        seen[col] = index + 1
        if index == 0:
            result.append(col)
        else:
            result.append(f"{col}_{index + 1}")
    return result


def read_excel_file(uploaded_file, normalize_columns: bool = True) -> pd.DataFrame:
    """Load Excel and remove empty rows/columns."""
    df = pd.read_excel(uploaded_file)
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df.columns = [str(col).strip() for col in df.columns]
    if normalize_columns:
        normalized = [_normalize_column_name(col) for col in df.columns]
        df.columns = _dedupe_columns(normalized)
    return df.reset_index(drop=True)


def _is_mostly_datetime(series: pd.Series, threshold: float = 0.7) -> bool:
    if series.empty:
        return False
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return float(parsed.notna().mean()) >= threshold


def _is_mostly_numeric(series: pd.Series, threshold: float = 0.75) -> bool:
    if series.empty:
        return False
    parsed = pd.to_numeric(series, errors="coerce")
    return float(parsed.notna().mean()) >= threshold


def build_column_profile(df: pd.DataFrame) -> ColumnProfile:
    all_columns = [str(col) for col in df.columns]
    numeric_columns: list[str] = []
    datetime_columns: list[str] = []
    categorical_columns: list[str] = []

    for column in all_columns:
        series = df[column]
        if pd.api.types.is_numeric_dtype(series) or _is_mostly_numeric(series):
            numeric_columns.append(column)
            continue
        if pd.api.types.is_datetime64_any_dtype(series) or _is_mostly_datetime(series):
            datetime_columns.append(column)
            continue
        categorical_columns.append(column)

    return ColumnProfile(
        all_columns=all_columns,
        numeric_columns=numeric_columns,
        datetime_columns=datetime_columns,
        categorical_columns=categorical_columns,
    )


def _pick_by_keywords(columns: list[str], keywords: list[str]) -> str:
    lowered = [(column, column.lower()) for column in columns]
    for column, lowered_column in lowered:
        if any(keyword in lowered_column for keyword in keywords):
            return column
    return NONE_OPTION


def suggest_default_map(profile: ColumnProfile) -> dict[str, str]:
    defaults = {
        "id": _pick_by_keywords(profile.all_columns, ["id", "codigo", "cod", "uuid"]),
        "date": _pick_by_keywords(profile.all_columns, ["data", "date", "dt"]),
        "value": _pick_by_keywords(profile.all_columns, ["valor", "value", "preco", "total"]),
        "category": _pick_by_keywords(profile.all_columns, ["categoria", "segmento", "canal"]),
        "status": _pick_by_keywords(profile.all_columns, ["status", "situacao", "estado"]),
    }

    if defaults["value"] == NONE_OPTION and profile.numeric_columns:
        defaults["value"] = profile.numeric_columns[0]
    if defaults["date"] == NONE_OPTION and profile.datetime_columns:
        defaults["date"] = profile.datetime_columns[0]
    if defaults["category"] == NONE_OPTION and profile.categorical_columns:
        defaults["category"] = profile.categorical_columns[0]

    return defaults


def prepare_analysis_dataframe(df: pd.DataFrame, column_map: dict[str, str]) -> pd.DataFrame:
    output = pd.DataFrame(index=df.index)
    for target, source in column_map.items():
        if source and source != NONE_OPTION and source in df.columns:
            output[target] = df[source]

    if "date" in output.columns:
        output["date"] = pd.to_datetime(output["date"], errors="coerce", dayfirst=True)
    if "value" in output.columns:
        output["value"] = pd.to_numeric(output["value"], errors="coerce")
    if "id" in output.columns:
        output["id"] = output["id"].astype("string")
    if "category" in output.columns:
        output["category"] = output["category"].astype("string").fillna("sem_valor")
    if "status" in output.columns:
        output["status"] = output["status"].astype("string").fillna("sem_valor")

    output["_row_id"] = output.index + 1
    return output
