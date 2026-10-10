# src/task/step/steps/_plot_helpers.py
"""Shared helpers for plotting steps."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


_STYLE_APPLIED = False


def setup_style() -> None:
    global _STYLE_APPLIED
    if _STYLE_APPLIED:
        return
    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "lines.linewidth": 1.0,
        "figure.dpi": 100,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.1,
    })
    _STYLE_APPLIED = True


def save_figure(fig, ctx, filename: str) -> str:
    """Save ``fig`` under ``output/figures/<filename>``.

    Returns the absolute path as a string.
    """
    fig_dir = ctx.out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    out_path = fig_dir / filename
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return str(out_path)