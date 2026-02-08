from __future__ import annotations

import pandas as pd


def safe_int(value) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def kpi_snapshot(df: pd.DataFrame) -> dict[str, float]:
    rows = len(df)
    core_columns = [column for column in df.columns if column != "_row_id"]
    if core_columns:
        mapped_rows = int(df[core_columns].notna().any(axis=1).sum())
    else:
        mapped_rows = rows

    value_sum = 0.0
    value_avg = 0.0
    if "value" in df.columns:
        value_sum = float(df["value"].fillna(0).sum())
        value_avg = float(df["value"].dropna().mean() or 0.0)

    null_rate = 0.0
    if rows > 0 and core_columns:
        null_rate = float(
            df[core_columns].isna().sum().sum() / (rows * max(len(core_columns), 1))
        )

    return {
        "rows": rows,
        "mapped_rows": mapped_rows,
        "value_sum": value_sum,
        "value_avg": value_avg,
        "null_rate": null_rate,
    }


def apply_date_filter(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    if "date" not in df.columns:
        return df
    filtered = df.copy()
    filtered = filtered[filtered["date"].notna()]
    if filtered.empty:
        return filtered
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return filtered[(filtered["date"] >= start) & (filtered["date"] <= end)]


def daily_aggregation(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns or "value" not in df.columns:
        return pd.DataFrame(columns=["day", "value_sum"])
    work = df[df["date"].notna()].copy()
    if work.empty:
        return pd.DataFrame(columns=["day", "value_sum"])
    work["day"] = work["date"].dt.date
    result = work.groupby("day", as_index=False)["value"].sum()
    return result.rename(columns={"value": "value_sum"})


def top_categories(df: pd.DataFrame, column: str, limit: int = 10) -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame(columns=[column, "count"])
    work = (
        df[column]
        .fillna("sem_valor")
        .astype(str)
        .value_counts(dropna=False)
        .head(limit)
        .rename_axis(column)
        .reset_index(name="count")
    )
    return work


def null_report(df: pd.DataFrame) -> pd.DataFrame:
    rows = max(len(df), 1)
    report = pd.DataFrame(
        {
            "coluna": df.columns,
            "nulos": [int(df[col].isna().sum()) for col in df.columns],
        }
    )
    report["perc_nulos"] = (report["nulos"] / rows * 100).round(2)
    return report.sort_values(by=["perc_nulos", "nulos"], ascending=False).reset_index(drop=True)
