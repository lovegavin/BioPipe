# src/task/step/steps/volcano.py
"""Volcano plot of a differential comparison result.

Input is a 2D form with a feature dim and a "statistic" dim that
carries the columns log2FC, P, and optionally Q_VALUE.

Points are classified by both thresholds:

    up       log2FC >  lfc_threshold and P < p_threshold
    down     log2FC < -lfc_threshold and P < p_threshold
    ns       everything else

Missing or non-finite rows are skipped.

Params:
    dim           : feature dim (default "gene")
    stat_dim      : statistic dim (default "statistic")
    lfc_label     : column label for log2FC (default "log2FC")
    p_label       : column label for P (default "P")
    lfc_threshold : |log2FC| cutoff (default 1.0)
    p_threshold   : P cutoff (default 0.05)
    filename      : output file name (required)
    title         : optional plot title
    xlabel        : optional x label (default: lfc_label)
    ylabel        : optional y label (default: "-log10(P)")
    point_size    : marker size (default 8)
    alpha         : marker transparency (default 0.7)
    label_top     : if > 0, annotate the top N most significant
                    points with their feature labels (default 0)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._plot_helpers import save_figure, setup_style


class VolcanoStep(Step):
    """Draw a volcano plot."""

    name = "volcano"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        form = inputs[0]
        dim = ctx.step_params.get("dim", "gene")
        stat_dim = ctx.step_params.get("stat_dim", "statistic")
        lfc_label = ctx.step_params.get("lfc_label", "log2FC")
        p_label = ctx.step_params.get("p_label", "P")
        lfc_threshold = float(
            ctx.step_params.get("lfc_threshold", 1.0)
        )
        p_threshold = float(ctx.step_params.get("p_threshold", 0.05))
        filename = ctx.step_params.get("filename")
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get("xlabel", lfc_label)
        ylabel = ctx.step_params.get("ylabel", "-log10(P)")
        point_size = float(ctx.step_params.get("point_size", 8))
        alpha = float(ctx.step_params.get("alpha", 0.7))
        label_top = int(ctx.step_params.get("label_top", 0))

        if not filename:
            raise StepError("volcano: 'filename' is required")
        if lfc_threshold < 0:
            raise StepError(
                f"volcano: lfc_threshold must be >= 0, "
                f"got {lfc_threshold}"
            )
        if not 0.0 < p_threshold <= 1.0:
            raise StepError(
                f"volcano: p_threshold must be in (0, 1], "
                f"got {p_threshold}"
            )
        if form.data.ndim != 2:
            raise StepError(
                f"volcano: input must be 2D, got ndim={form.data.ndim}"
            )
        for d, name in ((dim, "dim"), (stat_dim, "stat_dim")):
            if d not in form.dims:
                raise StepError(
                    f"volcano: {name} '{d}' not present. "
                    f"Available: {form.dims}"
                )

        feat_axis = form.dims.index(dim)
        stat_axis = form.dims.index(stat_dim)
        stat_labels = form.labels.get(stat_dim, {})
        for lbl, name in ((lfc_label, "lfc_label"), (p_label, "p_label")):
            if lbl not in stat_labels:
                raise StepError(
                    f"volcano: {name}='{lbl}' not in dim "
                    f"'{stat_dim}'. Available: {sorted(stat_labels)}"
                )

        lfc = np.take(
            form.data, stat_labels[lfc_label], axis=stat_axis
        ).astype(float)
        p = np.take(
            form.data, stat_labels[p_label], axis=stat_axis
        ).astype(float)

        if lfc.shape != p.shape:
            raise StepError(
                f"volcano: lfc and p have different shapes "
                f"{lfc.shape} vs {p.shape}"
            )

        feat_labels_map = form.labels.get(dim, {})
        pos_to_label = {v: k for k, v in feat_labels_map.items()}
        feat_names = [
            pos_to_label.get(i, f"#{i}") for i in range(lfc.shape[0])
        ]

        valid = (
            np.isfinite(lfc)
            & np.isfinite(p)
            & (p > 0)
            & (p <= 1)
        )
        n_total = int(lfc.size)
        n_valid = int(valid.sum())
        if n_valid == 0:
            raise StepError(
                f"volcano: no finite points in "
                f"(x={lfc_label}, y={p_label})"
            )

        lfc_v = lfc[valid]
        neg_log10p = -np.log10(p[valid])
        names_v = [feat_names[i] for i in np.where(valid)[0]]

        up_mask = (
            (lfc_v > lfc_threshold) & (p[valid] < p_threshold)
        )
        down_mask = (
            (lfc_v < -lfc_threshold) & (p[valid] < p_threshold)
        )
        ns_mask = ~(up_mask | down_mask)

        n_up = int(up_mask.sum())
        n_down = int(down_mask.sum())
        n_ns = int(ns_mask.sum())

        fig, ax = plt.subplots(figsize=(5.5, 4.5))

        ax.scatter(
            lfc_v[ns_mask], neg_log10p[ns_mask],
            s=point_size, alpha=alpha, c="#BFBFBF",
            edgecolors="none", rasterized=True, label="ns",
        )
        ax.scatter(
            lfc_v[up_mask], neg_log10p[up_mask],
            s=point_size, alpha=alpha, c="#D62728",
            edgecolors="none", rasterized=True,
            label=f"up ({n_up})",
        )
        ax.scatter(
            lfc_v[down_mask], neg_log10p[down_mask],
            s=point_size, alpha=alpha, c="#1F77B4",
            edgecolors="none", rasterized=True,
            label=f"down ({n_down})",
        )

        if lfc_threshold > 0:
            ax.axvline(
                lfc_threshold, color="black", lw=0.6, ls="--",
                alpha=0.5,
            )
            ax.axvline(
                -lfc_threshold, color="black", lw=0.6, ls="--",
                alpha=0.5,
            )
        ax.axhline(
            -np.log10(p_threshold), color="black", lw=0.6, ls="--",
            alpha=0.5,
        )

        annotated_labels: list[str] = []
        if label_top > 0:
            # Rank by P ascending; annotate the top N.
            p_v = p[valid]
            order = np.argsort(p_v)
            top_idx = order[:label_top]
            for i in top_idx:
                ax.annotate(
                    names_v[i],
                    xy=(lfc_v[i], neg_log10p[i]),
                    xytext=(3, 3),
                    textcoords="offset points",
                    fontsize=7,
                )
                annotated_labels.append(names_v[i])

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)
        ax.legend(frameon=False, loc="upper right", markerscale=1.2)

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "volcano",
            "filename": filename,
            "path": out_path,
            "dim": dim,
            "stat_dim": stat_dim,
            "lfc_label": lfc_label,
            "p_label": p_label,
            "lfc_threshold": lfc_threshold,
            "p_threshold": p_threshold,
            "n_total": n_total,
            "n_valid": n_valid,
            "n_up": n_up,
            "n_down": n_down,
            "n_ns": n_ns,
            "up_labels": [
                names_v[i] for i in np.where(up_mask)[0]
            ],
            "down_labels": [
                names_v[i] for i in np.where(down_mask)[0]
            ],
            "annotated_labels": annotated_labels,
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_valid": n_valid,
            "n_up": n_up,
            "n_down": n_down,
            "n_ns": n_ns,
            "path": out_path,
        }

        print(
            f"[volcano] {n_up} up / {n_down} down / {n_ns} ns "
            f"(out of {n_valid}) -> {out_path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data