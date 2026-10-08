"""Initial design-of-experiments (LHS / random feasible)."""

from __future__ import annotations

from typing import Any

import numpy as np

from doex.core.schema import CampaignSchema, Factor, FactorType


def _lhs_unit(n: int, d: int, rng: np.random.Generator) -> np.ndarray:
    """Simple Latin Hypercube in [0, 1]^d."""
    if d == 0:
        return np.zeros((n, 0))
    cut = np.linspace(0.0, 1.0, n + 1)
    u = rng.uniform(size=(n, d))
    points = np.empty((n, d))
    for j in range(d):
        pts = cut[:-1] + u[:, j] * (cut[1:] - cut[:-1])
        rng.shuffle(pts)
        points[:, j] = pts
    return points


def sample_factor(factor: Factor, u: float, rng: np.random.Generator) -> Any:
    """Map a unit sample u∈[0,1] (or draw) to a factor value."""
    if factor.type == FactorType.FIXED:
        return factor.fixed_value
    if factor.type == FactorType.CATEGORICAL:
        levels = factor.levels or []
        if not levels:
            raise ValueError(f"Categorical factor '{factor.name}' has no levels")
        idx = min(int(u * len(levels)), len(levels) - 1)
        return levels[idx]
    assert factor.bounds is not None
    lo, hi = factor.bounds
    if factor.type == FactorType.INTEGER:
        # inclusive integer range
        lo_i, hi_i = int(np.ceil(lo)), int(np.floor(hi))
        if hi_i < lo_i:
            lo_i, hi_i = int(lo), int(hi)
        n_levels = hi_i - lo_i + 1
        idx = min(int(u * n_levels), n_levels - 1)
        return lo_i + idx
    return float(lo + u * (hi - lo))


def sample_points(
    schema: CampaignSchema,
    n: int,
    *,
    seed: int = 42,
    method: str = "lhs",
) -> list[dict[str, Any]]:
    """Draw n feasible factor combinations."""
    rng = np.random.default_rng(seed)
    free = [f for f in schema.factors if f.type != FactorType.FIXED]
    d = len(free)
    if method == "random":
        unit = rng.random((n, max(d, 1)))
    else:
        unit = _lhs_unit(n, max(d, 1), rng)

    rows: list[dict[str, Any]] = []
    for i in range(n):
        vals: dict[str, Any] = {}
        for j, f in enumerate(free):
            u = float(unit[i, j]) if d else float(rng.random())
            vals[f.name] = sample_factor(f, u, rng)
        for f in schema.factors:
            if f.type == FactorType.FIXED:
                vals[f.name] = f.fixed_value
        rows.append(vals)
    return rows


def normalize_factor_vector(
    values: dict[str, Any],
    schema: CampaignSchema,
) -> np.ndarray:
    """Normalize free factors to roughly [0, 1] for distance metrics."""
    out: list[float] = []
    for f in schema.factors:
        if f.type == FactorType.FIXED:
            continue
        v = values.get(f.name)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out.append(0.5)
            continue
        if f.type == FactorType.CATEGORICAL:
            levels = f.levels or []
            if v in levels and len(levels) > 1:
                out.append(levels.index(v) / (len(levels) - 1))
            else:
                out.append(0.0)
        else:
            assert f.bounds is not None
            lo, hi = f.bounds
            span = hi - lo if hi != lo else 1.0
            out.append(float((float(v) - lo) / span))
    return np.asarray(out, dtype=float)
