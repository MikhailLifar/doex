"""Next-batch suggestion algorithms."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from doex.core.design import normalize_factor_vector, sample_points
from doex.core.schema import (
    CampaignSchema,
    FactorType,
    ResponseGoal,
    RunStatus,
    SuggestAlgorithm,
    SuggestSettings,
)
from doex.core.table import done_mask, factor_matrix


def _active_response(schema: CampaignSchema, settings: SuggestSettings) -> str | None:
    if settings.active_response and settings.active_response in schema.response_names():
        return settings.active_response
    for r in schema.responses:
        if r.goal != ResponseGoal.OBSERVE:
            return r.name
    return schema.responses[0].name if schema.responses else None


def _encode_Xy(
    df: pd.DataFrame,
    schema: CampaignSchema,
    response: str,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    mask = done_mask(df, response)
    sub = df.loc[mask]
    feature_names: list[str] = []
    cols: list[np.ndarray] = []
    for f in schema.factors:
        if f.type == FactorType.FIXED:
            continue
        feature_names.append(f.name)
        series = sub[f.name]
        if f.type == FactorType.CATEGORICAL:
            levels = f.levels or sorted(series.dropna().unique().tolist())
            mapping = {lv: i for i, lv in enumerate(levels)}
            cols.append(series.map(mapping).astype(float).to_numpy())
        else:
            cols.append(pd.to_numeric(series, errors="coerce").to_numpy(dtype=float))
    if not cols:
        X = np.zeros((len(sub), 0))
    else:
        X = np.column_stack(cols)
    y = pd.to_numeric(sub[response], errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(X).all(axis=1) & np.isfinite(y)
    return X[ok], y[ok], feature_names


def _candidates_to_matrix(
    candidates: list[dict[str, Any]],
    schema: CampaignSchema,
) -> np.ndarray:
    rows = []
    for c in candidates:
        row = []
        for f in schema.factors:
            if f.type == FactorType.FIXED:
                continue
            v = c[f.name]
            if f.type == FactorType.CATEGORICAL:
                levels = f.levels or []
                row.append(float(levels.index(v)) if v in levels else 0.0)
            else:
                row.append(float(v))
        rows.append(row)
    if not rows:
        return np.zeros((0, 0))
    return np.asarray(rows, dtype=float)


def _exploit_sign(goal: ResponseGoal) -> float:
    if goal == ResponseGoal.MINIMIZE:
        return -1.0
    return 1.0  # maximize / target / observe → higher predicted better for MVP


def _diversity_select(
    candidates: list[dict[str, Any]],
    scores: np.ndarray,
    schema: CampaignSchema,
    k: int,
    existing: list[dict[str, Any]] | None = None,
) -> list[tuple[dict[str, Any], float, str]]:
    """Greedy max-score with min-distance diversity."""
    if not candidates:
        return []
    norms = [normalize_factor_vector(c, schema) for c in candidates]
    chosen_idx: list[int] = []
    refs = [normalize_factor_vector(e, schema) for e in (existing or [])]

    remaining = list(range(len(candidates)))
    out: list[tuple[dict[str, Any], float, str]] = []
    while remaining and len(chosen_idx) < k:
        best_i = None
        best_val = -np.inf
        for i in remaining:
            pen = 0.0
            for j in chosen_idx:
                pen = max(pen, 1.0 / (1e-6 + np.linalg.norm(norms[i] - norms[j])))
            for r in refs:
                pen = max(pen, 0.5 / (1e-6 + np.linalg.norm(norms[i] - r)))
            val = float(scores[i]) - 0.05 * pen
            if val > best_val:
                best_val = val
                best_i = i
        assert best_i is not None
        chosen_idx.append(best_i)
        remaining.remove(best_i)
        out.append((candidates[best_i], float(scores[best_i]), ""))
    return out


def suggest_batch(
    df: pd.DataFrame,
    schema: CampaignSchema,
    settings: SuggestSettings,
    *,
    k: int | None = None,
) -> list[tuple[dict[str, Any], str]]:
    """
    Return list of (factor_values, reason_text) for proposed runs.

    Falls back to LHS/initial design when too few done points.
    """
    k = k if k is not None else settings.batch_size
    k = max(1, int(k))
    response = _active_response(schema, settings)
    n_done = int(done_mask(df, response).sum()) if response else 0

    use_model = (
        settings.algorithm in (SuggestAlgorithm.TREES, SuggestAlgorithm.RIDGE)
        and response is not None
        and n_done >= settings.n_min_for_model
    )

    if not use_model or settings.algorithm in (
        SuggestAlgorithm.LHS,
        SuggestAlgorithm.RANDOM,
    ):
        method = "random" if settings.algorithm == SuggestAlgorithm.RANDOM else "lhs"
        pts = sample_points(schema, k, seed=settings.seed + n_done, method=method)
        reason = "space-filling start" if n_done < settings.n_min_for_model else "LHS / fill"
        return [(p, reason) for p in pts]

    X, y, _ = _encode_Xy(df, schema, response)
    if len(y) < settings.n_min_for_model:
        pts = sample_points(schema, k, seed=settings.seed, method="lhs")
        return [(p, "space-filling start") for p in pts]

    resp = schema.get_response(response)
    sign = _exploit_sign(resp.goal)
    rng_seed = settings.seed + n_done

    candidates = sample_points(
        schema,
        settings.n_candidates,
        seed=rng_seed,
        method="lhs",
    )
    Xc = _candidates_to_matrix(candidates, schema)

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    Xcs = scaler.transform(Xc)

    if settings.algorithm == SuggestAlgorithm.RIDGE:
        model = Ridge(alpha=1.0, random_state=settings.seed)
        model.fit(Xs, y)
        mu = model.predict(Xcs)
        # distance-based explore
        done_norm = factor_matrix(df, schema, done_mask(df, response))
        explore = np.zeros(len(candidates))
        if done_norm.size:
            # crude: min distance in raw scaled space
            for i, row in enumerate(Xcs):
                dmin = np.min(np.linalg.norm(Xs - row, axis=1))
                explore[i] = dmin
        else:
            explore[:] = 1.0
        scores = sign * mu + settings.explore_lambda * explore
        reasons_base = "ridge exploit+explore"
    else:
        model = ExtraTreesRegressor(
            n_estimators=100,
            random_state=settings.seed,
            max_features="sqrt",
        )
        model.fit(Xs, y)
        # per-tree predictions for uncertainty
        tree_preds = np.stack([t.predict(Xcs) for t in model.estimators_], axis=0)
        mu = tree_preds.mean(axis=0)
        std = tree_preds.std(axis=0)
        scores = sign * mu + settings.explore_lambda * std
        reasons_base = "trees exploit+explore"

    # diversity vs existing done/proposed/queued points
    existing: list[dict[str, Any]] = []
    keep = {
        RunStatus.DONE.value,
        RunStatus.PROPOSED.value,
        RunStatus.QUEUED.value,
    }
    for _, row in df.iterrows():
        if str(row.get("status")) not in keep:
            continue
        existing.append({f.name: row.get(f.name) for f in schema.factors})

    selected = _diversity_select(candidates, scores, schema, k, existing=existing)
    out: list[tuple[dict[str, Any], str]] = []
    for vals, sc, _ in selected:
        # classify explore vs exploit by relative std/score contribution
        if settings.explore_lambda <= 0.15:
            tag = "exploit"
        elif settings.explore_lambda >= 1.0:
            tag = "explore"
        else:
            tag = "balanced"
        out.append((vals, f"{reasons_base} ({tag}, score={sc:.3f})"))
    return out


def predict_grid(
    df: pd.DataFrame,
    schema: CampaignSchema,
    settings: SuggestSettings,
    *,
    x_name: str,
    y_name: str,
    frozen: dict[str, Any] | None = None,
    resolution: int = 40,
    what: str = "response",
) -> dict[str, Any]:
    """
    Build a 2D grid of model prediction or acquisition for Maps tab.

    Returns dict with X, Y mesh, Z values, and metadata.
    """
    response = _active_response(schema, settings)
    fx = schema.get_factor(x_name)
    fy = schema.get_factor(y_name)
    if fx.bounds is None or fy.bounds is None:
        raise ValueError("2D slice requires continuous/integer axes with bounds")

    xs = np.linspace(fx.bounds[0], fx.bounds[1], resolution)
    ys = np.linspace(fy.bounds[0], fy.bounds[1], resolution)
    XX, YY = np.meshgrid(xs, ys)

    frozen = dict(frozen or {})
    for f in schema.factors:
        if f.name in (x_name, y_name):
            continue
        if f.name not in frozen:
            if f.type == FactorType.FIXED:
                frozen[f.name] = f.fixed_value
            elif f.type == FactorType.CATEGORICAL:
                frozen[f.name] = (f.levels or [None])[0]
            elif f.bounds is not None:
                frozen[f.name] = 0.5 * (f.bounds[0] + f.bounds[1])

    # Build candidate grid as factor dicts
    flat: list[dict[str, Any]] = []
    for iy in range(resolution):
        for ix in range(resolution):
            vals = dict(frozen)
            vals[x_name] = float(XX[iy, ix])
            vals[y_name] = float(YY[iy, ix])
            if fx.type == FactorType.INTEGER:
                vals[x_name] = int(round(vals[x_name]))
            if fy.type == FactorType.INTEGER:
                vals[y_name] = int(round(vals[y_name]))
            flat.append(vals)

    Z = np.full(XX.shape, np.nan, dtype=float)
    if response is None:
        return {"X": XX, "Y": YY, "Z": Z, "response": None, "what": what}

    n_done = int(done_mask(df, response).sum())
    if n_done < 2:
        return {
            "X": XX,
            "Y": YY,
            "Z": Z,
            "response": response,
            "what": what,
            "message": "Need at least 2 done points with response values",
        }

    X, y, _ = _encode_Xy(df, schema, response)
    if len(y) < 2:
        return {"X": XX, "Y": YY, "Z": Z, "response": response, "what": what}

    Xc = _candidates_to_matrix(flat, schema)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    Xcs = scaler.transform(Xc)

    resp = schema.get_response(response)
    sign = _exploit_sign(resp.goal)

    if settings.algorithm == SuggestAlgorithm.RIDGE:
        model = Ridge(alpha=1.0, random_state=settings.seed)
        model.fit(Xs, y)
        mu = model.predict(Xcs)
        std = np.zeros_like(mu)
    else:
        model = ExtraTreesRegressor(
            n_estimators=80,
            random_state=settings.seed,
            max_features="sqrt",
        )
        model.fit(Xs, y)
        tree_preds = np.stack([t.predict(Xcs) for t in model.estimators_], axis=0)
        mu = tree_preds.mean(axis=0)
        std = tree_preds.std(axis=0)

    if what == "acquisition":
        zflat = sign * mu + settings.explore_lambda * std
    else:
        zflat = mu

    Z = zflat.reshape(XX.shape)
    return {
        "X": XX,
        "Y": YY,
        "Z": Z,
        "response": response,
        "what": what,
        "x_name": x_name,
        "y_name": y_name,
    }
