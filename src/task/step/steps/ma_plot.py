# src/task/step/steps/ma_plot.py
"""MA plot of a differential comparison result.

X axis: A = (mean_a + mean_b) / 2
Y axis: M = log2FC
Points are colored by P < p_threshold.

Input is a 2D form with a feature dim and a "statistic" dim that
carries log2FC, mean_a, mean_b, and P.

Params:
    dim           : feature dim (default "gene")
    stat_dim      : statistic dim (default "statistic")
    lfc_label     : column label for log2FC (default "log2FC")
    mean_a_label  : column label for group A mean (default "mean_a")
    mean_b_label  : column label for group B mean (default "mean_b")
    p_label       : column label for P (default "P")
    p_threshold   : P cutoff for significance (default 0.05)
    filename      : output file name (required)
    title         : optional plot title
    xlabel        : optional x label (default "log2 mean")
    ylabel        : optional y label (default: lfc_label)
    point_size    : marker size (default 8)
    alpha         : marker transparency (default 0.7)
    label_top     : if > 0, annotate the top N most significant
                    points with their feature labels (default 0)
"""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.contracts import port, param
from src.task.step.steps._plot_helpers import save_figure, setup_style


from ._legacy_schemas import LEGACY_SCHEMAS

class MaPlotStep(Step):
    """Draw an MA plot."""

    name = "ma_plot"
    parameters_schema = LEGACY_SCHEMAS['ma_plot']
    legacy_parameters = False
    inputs_arity = 1
    outputs = []
    input_contracts = [port(ndim=2, dims=[param("dim", "gene"), param("stat_dim", "statistic")], labels=[{"dim": param("stat_dim", "statistic"), "values": [param("lfc_label", "log2FC"), param("p_label", "P"), param("mean_a_label", "mean_a"), param("mean_b_label", "mean_b")]}])]
    output_contract = {"mode": "none"}

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        form = inputs[0]
        dim = ctx.step_params.get("dim", "gene")
        stat_dim = ctx.step_params.get("stat_dim", "statistic")
        lfc_label = ctx.step_params.get("lfc_label", "log2FC")
        mean_a_label = ctx.step_params.get("mean_a_label", "mean_a")
        mean_b_label = ctx.step_params.get("mean_b_label", "mean_b")
        p_label = ctx.step_params.get("p_label", "P")
        p_threshold = float(ctx.step_params.get("p_threshold", 0.05))
        filename = ctx.step_params.get("filename")
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get("xlabel", "log2 mean")
        ylabel = ctx.step_params.get("ylabel", lfc_label)
        point_size = float(ctx.step_params.get("point_size", 8))
        alpha = float(ctx.step_params.get("alpha", 0.7))
        label_top = int(ctx.step_params.get("label_top", 0))

        if not filename:
            raise StepError("ma_plot: 'filename' is required")
        if not 0.0 < p_threshold <= 1.0:
            raise StepError(
                f"ma_plot: p_threshold must be in (0, 1], "
                f"got {p_threshold}"
            )
        if form.data.ndim != 2:
            raise StepError(
                f"ma_plot: input must be 2D, got ndim={form.data.ndim}"
            )
        for d, name in ((dim, "dim"), (stat_dim, "stat_dim")):
            if d not in form.dims:
                raise StepError(
                    f"ma_plot: {name} '{d}' not present. "
                    f"Available: {form.dims}"
                )

        stat_axis = form.dims.index(stat_dim)
        stat_labels = form.labels.get(stat_dim, {})
        for lbl, name in (
            (lfc_label, "lfc_label"),
            (mean_a_label, "mean_a_label"),
            (mean_b_label, "mean_b_label"),
            (p_label, "p_label"),
        ):
            if lbl not in stat_labels:
                raise StepError(
                    f"ma_plot: {name}='{lbl}' not in dim "
                    f"'{stat_dim}'. Available: {sorted(stat_labels)}"
                )

        lfc = np.take(
            form.data, stat_labels[lfc_label], axis=stat_axis
        ).astype(float)
        mean_a = np.take(
            form.data, stat_labels[mean_a_label], axis=stat_axis
        ).astype(float)
        mean_b = np.take(
            form.data, stat_labels[mean_b_label], axis=stat_axis
        ).astype(float)
        p = np.take(
            form.data, stat_labels[p_label], axis=stat_axis
        ).astype(float)

        feat_labels_map = form.labels.get(dim, {})
        pos_to_label = {v: k for k, v in feat_labels_map.items()}
        feat_names = [
            pos_to_label.get(i, f"#{i}") for i in range(lfc.shape[0])
        ]

        with np.errstate(invalid="ignore", divide="ignore"):
            a = np.log2((mean_a + mean_b) / 2.0 + 1.0)

        valid = (
            np.isfinite(a)
            & np.isfinite(lfc)
            & np.isfinite(p)
            & (p > 0)
            & (p <= 1)
        )
        n_total = int(lfc.size)
        n_valid = int(valid.sum())
        if n_valid == 0:
            raise StepError(
                f"ma_plot: no finite points in "
                f"(x=log2 mean, y={lfc_label}, p={p_label})"
            )

        a_v = a[valid]
        lfc_v = lfc[valid]
        p_v = p[valid]
        names_v = [feat_names[i] for i in np.where(valid)[0]]

        sig_mask = p_v < p_threshold
        ns_mask = ~sig_mask
        n_sig = int(sig_mask.sum())
        n_ns = int(ns_mask.sum())

        fig, ax = plt.subplots(figsize=(5.5, 4.5))

        ax.scatter(
            a_v[ns_mask], lfc_v[ns_mask],
            s=point_size, alpha=alpha, c="#BFBFBF",
            edgecolors="none", rasterized=True,
            label=f"ns ({n_ns})",
        )
        ax.scatter(
            a_v[sig_mask], lfc_v[sig_mask],
            s=point_size, alpha=alpha, c="#D62728",
            edgecolors="none", rasterized=True,
            label=f"P < {p_threshold:g} ({n_sig})",
        )

        ax.axhline(0.0, color="black", lw=0.6, ls="--", alpha=0.5)

        annotated_labels: list[str] = []
        if label_top > 0:
            order = np.argsort(p_v)
            top_idx = order[:label_top]
            for i in top_idx:
                ax.annotate(
                    names_v[i],
                    xy=(a_v[i], lfc_v[i]),
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
            "kind": "ma_plot",
            "filename": filename,
            "path": out_path,
            "dim": dim,
            "stat_dim": stat_dim,
            "lfc_label": lfc_label,
            "mean_a_label": mean_a_label,
            "mean_b_label": mean_b_label,
            "p_label": p_label,
            "p_threshold": p_threshold,
            "n_total": n_total,
            "n_valid": n_valid,
            "n_significant": n_sig,
            "n_ns": n_ns,
            "significant_labels": [
                names_v[i] for i in np.where(sig_mask)[0]
            ],
            "annotated_labels": annotated_labels,
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_valid": n_valid,
            "n_significant": n_sig,
            "n_ns": n_ns,
            "path": out_path,
        }

        print(
            f"[ma_plot] {n_sig} significant / {n_ns} ns "
            f"(out of {n_valid}) -> {out_path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data