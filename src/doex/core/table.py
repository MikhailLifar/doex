"""Runs table helpers (pandas-backed)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from doex.core.schema import CampaignSchema, RunStatus, SourceTag

META_COLS = ("run_id", "sample_id", "status", "note", "source_tag", "reason")


def empty_runs(schema: CampaignSchema) -> pd.DataFrame:
    cols = list(META_COLS) + schema.factor_names() + schema.response_names()
    return pd.DataFrame(columns=cols)


def ensure_meta_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "run_id" not in out.columns:
        out.insert(0, "run_id", [f"R{i+1:04d}" for i in range(len(out))])
    if "sample_id" not in out.columns:
        out["sample_id"] = out["run_id"]
    if "status" not in out.columns:
        out["status"] = RunStatus.DONE.value
    if "note" not in out.columns:
        out["note"] = ""
    if "source_tag" not in out.columns:
        out["source_tag"] = SourceTag.EXPERIMENT.value
    if "reason" not in out.columns:
        out["reason"] = ""
    out["status"] = out["status"].fillna(RunStatus.DONE.value).astype(str)
    out["note"] = out["note"].fillna("").astype(str)
    out["source_tag"] = out["source_tag"].fillna(SourceTag.EXPERIMENT.value).astype(str)
    out["reason"] = out["reason"].fillna("").astype(str)
    out["sample_id"] = out["sample_id"].fillna(out["run_id"]).astype(str)
    return out


def align_to_schema(df: pd.DataFrame, schema: CampaignSchema) -> pd.DataFrame:
    out = ensure_meta_columns(df)
    for name in schema.factor_names() + schema.response_names():
        if name not in out.columns:
            out[name] = np.nan
    ordered = list(META_COLS) + schema.factor_names() + schema.response_names()
    extra = [c for c in out.columns if c not in ordered]
    return out[ordered + extra]


def next_run_id(df: pd.DataFrame) -> str:
    existing = set(df["run_id"].astype(str)) if "run_id" in df.columns and len(df) else set()
    i = len(existing) + 1
    while f"R{i:04d}" in existing:
        i += 1
    return f"R{i:04d}"


def count_by_status(df: pd.DataFrame) -> dict[str, int]:
    if df is None or len(df) == 0 or "status" not in df.columns:
        return {s.value: 0 for s in RunStatus}
    counts = df["status"].value_counts().to_dict()
    return {s.value: int(counts.get(s.value, 0)) for s in RunStatus}


def done_mask(df: pd.DataFrame, response: str | None = None) -> pd.Series:
    mask = df["status"].astype(str) == RunStatus.DONE.value
    if response is not None and response in df.columns:
        mask = mask & df[response].notna()
    return mask


def factor_matrix(
    df: pd.DataFrame,
    schema: CampaignSchema,
    mask: pd.Series | None = None,
) -> np.ndarray:
    """Return numeric matrix for free continuous/integer factors (categoricals encoded)."""
    sub = df if mask is None else df.loc[mask]
    cols: list[np.ndarray] = []
    for f in schema.factors:
        if f.type.value == "fixed":
            continue
        series = sub[f.name] if f.name in sub.columns else pd.Series([np.nan] * len(sub))
        if f.type.value == "categorical":
            levels = f.levels or sorted(series.dropna().unique().tolist())
            level_to_i = {lv: i for i, lv in enumerate(levels)}
            cols.append(series.map(level_to_i).astype(float).to_numpy())
        else:
            cols.append(pd.to_numeric(series, errors="coerce").to_numpy(dtype=float))
    if not cols:
        return np.zeros((len(sub), 0), dtype=float)
    return np.column_stack(cols)


def row_from_values(
    schema: CampaignSchema,
    factor_values: dict[str, Any],
    *,
    run_id: str,
    status: RunStatus = RunStatus.PROPOSED,
    sample_id: str | None = None,
    reason: str = "",
    source_tag: SourceTag = SourceTag.PROPOSED,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "run_id": run_id,
        "sample_id": sample_id or run_id,
        "status": status.value,
        "note": "",
        "source_tag": source_tag.value,
        "reason": reason,
    }
    for f in schema.factors:
        if f.type.value == "fixed":
            row[f.name] = f.fixed_value
        else:
            row[f.name] = factor_values.get(f.name)
    for r in schema.responses:
        row[r.name] = None
    return row
