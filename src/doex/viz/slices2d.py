"""2D scatter and model-slice plotting helpers (matplotlib)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from doex.core.schema import CampaignSchema, RunStatus


STATUS_COLORS = {
    RunStatus.DONE.value: "#2a6f6f",
    RunStatus.PROPOSED.value: "#c45c26",
    RunStatus.QUEUED.value: "#3d5a80",
    RunStatus.REJECTED.value: "#8a8a8a",
}


def plot_scatter(
    ax: Axes,
    df: pd.DataFrame,
    schema: CampaignSchema,
    *,
    x_name: str,
    y_name: str,
    color_by: str = "status",
) -> None:
    ax.clear()
    if df is None or len(df) == 0:
        ax.set_title("No runs yet")
        ax.set_xlabel(x_name)
        ax.set_ylabel(y_name)
        return

    x = pd.to_numeric(df[x_name], errors="coerce") if x_name in df.columns else pd.Series(dtype=float)
    y = pd.to_numeric(df[y_name], errors="coerce") if y_name in df.columns else pd.Series(dtype=float)

    if color_by == "status" or color_by not in df.columns:
        for status, color in STATUS_COLORS.items():
            mask = (df["status"].astype(str) == status) & x.notna() & y.notna()
            if mask.any():
                ax.scatter(
                    x[mask],
                    y[mask],
                    c=color,
                    label=status,
                    s=42,
                    edgecolors="white",
                    linewidths=0.4,
                    zorder=3,
                )
        ax.legend(loc="best", fontsize=8, frameon=False)
    else:
        cvals = pd.to_numeric(df[color_by], errors="coerce")
        mask = x.notna() & y.notna() & cvals.notna()
        sc = ax.scatter(
            x[mask],
            y[mask],
            c=cvals[mask],
            cmap="viridis",
            s=42,
            edgecolors="white",
            linewidths=0.4,
            zorder=3,
        )
        ax.figure.colorbar(sc, ax=ax, fraction=0.046, pad=0.04, label=color_by)

    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name)
    ax.set_title(f"{x_name} vs {y_name}")
    ax.grid(True, alpha=0.25)


def plot_slice(
    ax: Axes,
    grid: dict[str, Any],
    df: pd.DataFrame | None = None,
    *,
    overlay_points: bool = True,
) -> None:
    ax.clear()
    X = grid["X"]
    Y = grid["Y"]
    Z = grid["Z"]
    x_name = grid.get("x_name", "x")
    y_name = grid.get("y_name", "y")
    what = grid.get("what", "response")
    response = grid.get("response") or ""

    if np.all(np.isnan(Z)):
        msg = grid.get("message") or "Model slice unavailable"
        ax.text(0.5, 0.5, msg, ha="center", va="center", transform=ax.transAxes)
        ax.set_xlabel(x_name)
        ax.set_ylabel(y_name)
        ax.set_title(msg)
        return

    levels = 16
    cf = ax.contourf(X, Y, Z, levels=levels, cmap="mako" if False else "viridis", alpha=0.9)
    ax.figure.colorbar(cf, ax=ax, fraction=0.046, pad=0.04)

    if overlay_points and df is not None and len(df) and x_name in df.columns and y_name in df.columns:
        xs = pd.to_numeric(df[x_name], errors="coerce")
        ys = pd.to_numeric(df[y_name], errors="coerce")
        for status, color in STATUS_COLORS.items():
            mask = (df["status"].astype(str) == status) & xs.notna() & ys.notna()
            if mask.any():
                ax.scatter(
                    xs[mask],
                    ys[mask],
                    c=color,
                    s=28,
                    edgecolors="white",
                    linewidths=0.5,
                    zorder=4,
                    label=status,
                )
        ax.legend(loc="best", fontsize=7, frameon=False)

    title = f"{'Acquisition' if what == 'acquisition' else 'Model'}: {response}"
    ax.set_title(title)
    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name)


def export_figure(fig: Figure, path: str) -> None:
    fig.savefig(path, dpi=140, bbox_inches="tight")
