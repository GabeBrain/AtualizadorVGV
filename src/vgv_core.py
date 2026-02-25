from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
import warnings

import pandas as pd

from src.vgv_parser import normalize_text


DEFAULT_STATUS_COLOR = [31, 78, 122, 170]


def source_token(
    source_mode: str | None,
    source_name: str | None,
    source_bytes: bytes | None,
    sample_path: Path,
) -> str | None:
    if source_mode == "upload" and source_bytes:
        return f"upload:{source_name or '-'}:{len(source_bytes)}:{hash(source_bytes)}"

    if source_mode == "sample" and sample_path.exists():
        sample_stat = sample_path.stat()
        return f"sample:{sample_path.name}:{sample_stat.st_size}:{int(sample_stat.st_mtime_ns)}"

    return None


def find_column(columns: list[str], candidates: list[str]) -> str | None:
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


def format_number(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def format_decimal(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(value)


def format_brl(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    return "R$ " + format_decimal(value)


def format_decimal_variable(value: Any, precision: int = 1) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    try:
        raw = f"{float(value):,.{precision}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(value)

    if "," in raw:
        left, right = raw.split(",", 1)
        right = right.rstrip("0")
        return f"{left},{right}" if right else left
    return raw


def format_brl_compact(value: Any, precision: int = 1) -> str:
    if value is None:
        return "-"
    try:
        if pd.isna(value):
            return "-"
    except Exception:
        pass

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)

    abs_numeric = abs(numeric)
    if abs_numeric >= 1_000_000_000:
        scaled = numeric / 1_000_000_000
        suffix = "bilh\u00e3o" if abs(scaled) < 2 else "bilh\u00f5es"
        return f"R$ {format_decimal_variable(scaled, precision)} {suffix}"
    if abs_numeric >= 1_000_000:
        scaled = numeric / 1_000_000
        suffix = "milh\u00e3o" if abs(scaled) < 2 else "milh\u00f5es"
        return f"R$ {format_decimal_variable(scaled, precision)} {suffix}"
    if abs_numeric >= 1_000:
        scaled = numeric / 1_000
        return f"R$ {format_decimal_variable(scaled, precision)} mil"
    return format_brl(numeric)


def display_value_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        if pd.isna(value):
            return "-"
    except Exception:
        pass

    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return str(value)

    return str(value)


def to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            safe_name = str(sheet_name)[:31] or "Sheet1"
            frame.to_excel(writer, index=False, sheet_name=safe_name)
    return output.getvalue()


def _selection_payload(event: Any) -> Any:
    if event is None:
        return None
    if isinstance(event, dict):
        return event.get("selection", event)

    selection = getattr(event, "selection", None)
    if selection is not None:
        return selection

    return event


def _flatten_selection_items(value: Any) -> list[Any]:
    items: list[Any] = []
    stack = [value]

    while stack:
        current = stack.pop()
        if current is None:
            continue

        if isinstance(current, (list, tuple, set)):
            stack.extend(list(current))
            continue

        if isinstance(current, dict):
            items.append(current)
            stack.extend(list(current.values()))
            continue

        items.append(current)

    return items


def selection_index_from_event(event: Any) -> int | None:
    payload = _selection_payload(event)
    if payload is None:
        return None

    for item in _flatten_selection_items(payload):
        if isinstance(item, int):
            return item

        if isinstance(item, dict):
            for key in ("index", "row", "id"):
                value = item.get(key)
                if isinstance(value, int):
                    return value

    return None


def selection_name_from_event(event: Any) -> str | None:
    payload = _selection_payload(event)
    if payload is None:
        return None

    name_keys = ("Empreendimento", "empreendimento", "name", "nome")

    for item in _flatten_selection_items(payload):
        if isinstance(item, dict):
            for key in name_keys:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    return None


def clean_options(series: pd.Series) -> list[str]:
    values = [str(v) for v in series.dropna().astype(str).tolist() if str(v).strip()]
    return sorted(set(values))


def status_color(status_value: Any) -> list[int]:
    if status_value is None:
        return DEFAULT_STATUS_COLOR
    try:
        if pd.isna(status_value):
            return DEFAULT_STATUS_COLOR
    except Exception:
        pass

    status_norm = normalize_text(status_value)
    if "esgotado" in status_norm:
        return [176, 0, 32, 180]
    if "ativo" in status_norm:
        return [91, 117, 55, 180]
    return DEFAULT_STATUS_COLOR


def map_style_light(pdk_module: Any) -> str:
    styles = getattr(pdk_module, "map_styles", None)
    if styles is not None and hasattr(styles, "LIGHT"):
        return getattr(styles, "LIGHT")
    return "light"


def load_index_series(path_text: str, sheet_name: str, column_name: str) -> pd.DataFrame:
    if not path_text or not Path(path_text).exists():
        return pd.DataFrame(columns=["MesData", column_name])

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Workbook contains no default style, apply openpyxl's default",
            category=UserWarning,
        )
        raw = pd.read_excel(path_text, sheet_name=sheet_name, header=1)

    if raw.empty or raw.shape[1] < 2:
        return pd.DataFrame(columns=["MesData", column_name])

    date_col = raw.columns[0]
    index_col = raw.columns[1]

    frame = raw[[date_col, index_col]].rename(columns={date_col: "MesData", index_col: column_name}).copy()
    frame["MesData"] = pd.to_datetime(frame["MesData"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    frame[column_name] = pd.to_numeric(frame[column_name], errors="coerce")
    frame = frame.dropna(subset=["MesData", column_name]).sort_values("MesData")
    frame = frame.drop_duplicates(subset=["MesData"], keep="last")
    return frame.reset_index(drop=True)


def load_incc_series(path_text: str) -> pd.DataFrame:
    return load_index_series(path_text=path_text, sheet_name="INCC-DI", column_name="INCC-DI")


def resolve_base_index(index_df: pd.DataFrame, column: str, target_date: pd.Timestamp) -> tuple[float | None, pd.Timestamp | None]:
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


def build_reajuste_dataset(
    perf_source: pd.DataFrame,
    incc_path_text: str,
    target_months: tuple[str, ...] | None,
    base_date_text: str,
    fallback_base_date: pd.Timestamp,
    extra_index_sources: tuple[tuple[str, str, str], ...] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    index_sources: list[tuple[str, str, str]] = [("INCC-DI", incc_path_text, "INCC-DI")]
    for source in list(extra_index_sources or ()):
        if not isinstance(source, (list, tuple)) or len(source) < 3:
            continue
        index_name = str(source[0]).strip()
        path_text = str(source[1]).strip()
        sheet_name = str(source[2]).strip()
        if index_name:
            index_sources.append((index_name, path_text, sheet_name))

    seen_indices: set[str] = set()
    normalized_sources: list[tuple[str, str, str]] = []
    for index_name, path_text, sheet_name in index_sources:
        if index_name in seen_indices:
            continue
        seen_indices.add(index_name)
        normalized_sources.append((index_name, path_text, sheet_name))

    requested_indices = [item[0] for item in normalized_sources]
    empty_columns = [
        "__registro_id",
        "Empreendimento",
        "Mes",
        "MesData",
        "VGV Nominal",
    ]
    for index_name in requested_indices:
        empty_columns.append(index_name)
        empty_columns.append(f"VGV Corrigido {index_name}")
    empty_frame = pd.DataFrame(columns=empty_columns)

    base_date = pd.to_datetime(base_date_text, errors="coerce")
    if pd.isna(base_date):
        base_date = fallback_base_date

    index_frames: dict[str, pd.DataFrame] = {}
    for index_name, path_text, sheet_name in normalized_sources:
        try:
            series_frame = load_index_series(path_text=path_text, sheet_name=sheet_name, column_name=index_name)
        except Exception:
            series_frame = pd.DataFrame(columns=["MesData", index_name])
        if not series_frame.empty:
            index_frames[index_name] = series_frame

    base_values: dict[str, float | None] = {}
    base_dates: dict[str, pd.Timestamp | None] = {}
    for index_name, series_frame in index_frames.items():
        base_value, base_value_date = resolve_base_index(series_frame, index_name, pd.Timestamp(base_date))
        base_values[index_name] = base_value
        base_dates[index_name] = base_value_date

    missing_indices = [index_name for index_name in requested_indices if index_name not in index_frames]
    meta: dict[str, Any] = {
        "reference_date": pd.Timestamp(base_date),
        "target_months": list(target_months) if target_months else [],
        "available_indices": list(index_frames.keys()),
        "missing_indices": missing_indices,
        "base_values": base_values,
        "base_dates": base_dates,
    }
    if "INCC-DI" in base_values:
        meta["base_di"] = base_values.get("INCC-DI")
        meta["base_di_date"] = base_dates.get("INCC-DI")

    if not index_frames:
        return empty_frame, meta

    perf = perf_source.copy()
    if perf.empty:
        return empty_frame, meta

    if "MesData" not in perf.columns and "Mes" in perf.columns:
        perf["MesData"] = pd.to_datetime("01/" + perf["Mes"].astype(str), format="%d/%m/%Y", errors="coerce")
    if "Mes" not in perf.columns and "MesData" in perf.columns:
        perf["Mes"] = pd.to_datetime(perf["MesData"], errors="coerce").dt.strftime("%m/%Y")

    empreendimento_col = find_column(list(perf.columns), ["Empreendimento"])
    vgv_col = find_column(list(perf.columns), ["VGV Oferta Final"])

    if not empreendimento_col or not vgv_col or "Mes" not in perf.columns or "MesData" not in perf.columns:
        return empty_frame, meta

    if "__registro_id" not in perf.columns:
        perf["__registro_id"] = range(1, len(perf) + 1)

    perf[vgv_col] = pd.to_numeric(perf[vgv_col], errors="coerce")
    perf = perf.dropna(subset=["MesData", vgv_col])
    if target_months:
        perf = perf[perf["Mes"].isin(list(target_months))].copy()

    if perf.empty:
        return empty_frame, meta

    monthly = (
        perf.groupby(["__registro_id", empreendimento_col, "Mes", "MesData"], as_index=False)[vgv_col]
        .sum()
        .rename(columns={empreendimento_col: "Empreendimento", vgv_col: "VGV Nominal"})
    )

    for index_name, series_frame in index_frames.items():
        monthly = monthly.merge(series_frame, on="MesData", how="left")

    for index_name in requested_indices:
        corrected_col = f"VGV Corrigido {index_name}"
        base_value = base_values.get(index_name)
        if base_value is not None and index_name in monthly.columns:
            monthly[corrected_col] = monthly["VGV Nominal"] * base_value / monthly[index_name].replace(0, pd.NA)
        else:
            monthly[corrected_col] = pd.NA

    monthly = monthly.sort_values(["Empreendimento", "MesData"]).reset_index(drop=True)
    return monthly, meta
