"""Import / export for tables and campaign packages."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from doex.core.schema import CampaignSchema, ColumnMapping, Factor, FactorType, Response, ResponseGoal
from doex.core.table import align_to_schema, ensure_meta_columns


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".xlsx", ".xls"):
        try:
            return pd.read_excel(path)
        except ImportError as exc:
            raise ImportError(
                "Reading Excel requires openpyxl. Install it or export CSV."
            ) from exc
    raise ValueError(f"Unsupported table format: {suffix}")


def write_runs_csv(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def infer_schema_from_df(
    df: pd.DataFrame,
    mapping: ColumnMapping,
) -> CampaignSchema:
    """Build a schema from a mapping and data preview."""
    factors: list[Factor] = []
    responses: list[Response] = []

    for fname, col in mapping.factors.items():
        series = df[col]
        ftype_s = mapping.factor_types.get(fname)
        if ftype_s:
            ftype = FactorType(ftype_s)
        elif pd.api.types.is_numeric_dtype(series):
            ftype = FactorType.CONTINUOUS
        else:
            ftype = FactorType.CATEGORICAL

        if ftype == FactorType.CATEGORICAL:
            levels = sorted(series.dropna().astype(str).unique().tolist())
            factors.append(Factor(name=fname, type=ftype, levels=levels))
        else:
            numeric = pd.to_numeric(series, errors="coerce")
            lo = float(numeric.min()) if numeric.notna().any() else 0.0
            hi = float(numeric.max()) if numeric.notna().any() else 1.0
            if lo == hi:
                hi = lo + 1.0
            # pad bounds slightly so future proposals can explore nearby
            pad = 0.05 * (hi - lo)
            factors.append(
                Factor(name=fname, type=ftype, bounds=(lo - pad, hi + pad))
            )

    for rname, col in mapping.responses.items():
        goal_s = mapping.response_goals.get(rname, "maximize")
        responses.append(Response(name=rname, goal=ResponseGoal(goal_s)))

    schema = CampaignSchema(factors=factors, responses=responses)
    schema.validate()
    return schema


def apply_mapping(df: pd.DataFrame, mapping: ColumnMapping, schema: CampaignSchema) -> pd.DataFrame:
    """Rename/select columns according to mapping into a runs table."""
    data: dict[str, Any] = {}
    if mapping.sample_id and mapping.sample_id in df.columns:
        data["sample_id"] = df[mapping.sample_id].astype(str)
    for fname, col in mapping.factors.items():
        data[fname] = df[col]
    for rname, col in mapping.responses.items():
        data[rname] = df[col]
    out = pd.DataFrame(data)
    out = ensure_meta_columns(out)
    return align_to_schema(out, schema)


def guess_mapping(df: pd.DataFrame) -> ColumnMapping:
    """Heuristic: last numeric columns as responses if named like H_/E_/hardness…"""
    cols = list(df.columns)
    sample_id = None
    for c in cols:
        cl = str(c).lower()
        if cl in ("sample_id", "sample", "id", "run_id"):
            sample_id = c
            break

    response_hints = ("hardness", "modulus", "h_gpa", "e_gpa", "response", "y_", "target")
    factors: dict[str, str] = {}
    responses: dict[str, str] = {}

    for c in cols:
        if c == sample_id:
            continue
        cl = str(c).lower()
        if any(h in cl for h in response_hints) or cl in ("h_gpa", "e_gpa"):
            responses[str(c)] = c
        elif pd.api.types.is_numeric_dtype(df[c]) or df[c].dtype == object:
            factors[str(c)] = c

    # If no response guessed, treat last numeric col as response
    if not responses:
        numeric_cols = [c for c in cols if c != sample_id and pd.api.types.is_numeric_dtype(df[c])]
        if numeric_cols:
            c = numeric_cols[-1]
            responses[str(c)] = c
            factors.pop(str(c), None)

    return ColumnMapping(factors=factors, responses=responses, sample_id=sample_id)


def save_campaign_dir(
    path: str | Path,
    meta: dict[str, Any],
    runs: pd.DataFrame,
) -> Path:
    """
    Persist campaign as a directory:

        <path>/
          campaign.json   # meta + schema + settings + history
          runs.csv
    """
    path = Path(path)
    if path.suffix.lower() == ".doex":
        # treat as directory named *.doex
        pass
    path.mkdir(parents=True, exist_ok=True)
    write_runs_csv(runs, path / "runs.csv")
    with open(path / "campaign.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)
    # marker for recognition
    (path / ".doex").write_text("doex-campaign-dir\n", encoding="utf-8")
    return path


def load_campaign_dir(path: str | Path) -> tuple[dict[str, Any], pd.DataFrame]:
    path = Path(path)
    meta_path = path / "campaign.json"
    runs_path = path / "runs.csv"
    if not meta_path.exists():
        raise FileNotFoundError(f"No campaign.json in {path}")
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    runs = pd.read_csv(runs_path) if runs_path.exists() else pd.DataFrame()
    return meta, runs


def export_schema_json(schema: CampaignSchema, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(schema.to_dict(), fh, indent=2)


def copy_campaign(src: str | Path, dst: str | Path) -> Path:
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst
