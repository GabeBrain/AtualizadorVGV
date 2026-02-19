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


def load_incc_series(path_text: str) -> pd.DataFrame:
    def _read_sheet(sheet_name: str) -> pd.DataFrame:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Workbook contains no default style, apply openpyxl's default",
                category=UserWarning,
            )
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
    di = di.sort_values("MesData").drop_duplicates(subset=["MesData"], keep="last")
    return di.reset_index(drop=True)


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
) -> tuple[pd.DataFrame, dict[str, Any]]:
    empty_columns = [
        "__registro_id",
        "Empreendimento",
        "Mes",
        "MesData",
        "VGV Nominal",
        "INCC-DI",
        "VGV Corrigido INCC-DI",
    ]
    empty_frame = pd.DataFrame(columns=empty_columns)

    incc_df = load_incc_series(incc_path_text)
    if incc_df.empty:
        return empty_frame, {}

    base_date = pd.to_datetime(base_date_text, errors="coerce")
    if pd.isna(base_date):
        base_date = fallback_base_date

    base_di, base_di_date = resolve_base_index(incc_df, "INCC-DI", base_date)
    meta: dict[str, Any] = {
        "base_di": base_di,
        "base_di_date": base_di_date,
        "reference_date": pd.Timestamp(base_date),
        "target_months": list(target_months) if target_months else [],
    }

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

    monthly = monthly.merge(incc_df, on="MesData", how="left")

    if base_di is not None and "INCC-DI" in monthly.columns:
        monthly["VGV Corrigido INCC-DI"] = monthly["VGV Nominal"] * base_di / monthly["INCC-DI"].replace(0, pd.NA)
    else:
        monthly["VGV Corrigido INCC-DI"] = pd.NA

    monthly = monthly.sort_values(["Empreendimento", "MesData"]).reset_index(drop=True)
    return monthly, meta
