# src/task/step/steps/scatter.py
"""Scatter plot operator.

Input is a single 2D form. One dimension of the form holds the
attributes (columns); the other dimension holds the observations
(points).

The operator reads two labeled columns as x and y, optionally a third
as a color group, and writes a scatter plot to ``output/figures/``.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._plot_helpers import save_figure, setup_style


class ScatterStep(Step):
    """Draw a scatter plot.

    Params:
        dim         : attribute dimension (default "feature")
        x_label     : column label for the x axis
        y_label     : column label for the y axis
        color_label : optional column label for grouping
        filename    : output file name (e.g. "pca.png")
        title       : optional plot title
        xlabel      : optional x-axis label (default: x_label)
        ylabel      : optional y-axis label (default: y_label)
        point_size  : marker size (default 8)
        alpha       : marker transparency (default 0.7)
    """

    name = "scatter"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        form = inputs[0]
        dim = ctx.step_params.get("dim", "feature")
        x_label = ctx.step_params["x_label"]
        y_label = ctx.step_params["y_label"]
        color_label = ctx.step_params.get("color_label")
        filename = ctx.step_params["filename"]
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get("xlabel", x_label)
        ylabel = ctx.step_params.get("ylabel", y_label)
        point_size = float(ctx.step_params.get("point_size", 8))
        alpha = float(ctx.step_params.get("alpha", 0.7))

        if form.data.ndim != 2:
            raise StepError(
                f"scatter requires a 2D form, got ndim={form.data.ndim}"
            )
        if dim not in form.dims:
            raise StepError(
                f"Dim '{dim}' not present. Available: {form.dims}"
            )

        attr_axis = form.dims.index(dim)
        labels = form.labels[dim]

        for lbl, name in ((x_label, "x_label"), (y_label, "y_label")):
            if lbl not in labels:
                raise StepError(
                    f"scatter: {name}='{lbl}' not in dim '{dim}'. "
                    f"Available: {sorted(labels)}"
                )
        if color_label is not None and color_label not in labels:
            raise StepError(
                f"scatter: color_label='{color_label}' not in dim "
                f"'{dim}'. Available: {sorted(labels)}"
            )

        x = np.take(form.data, labels[x_label], axis=attr_axis).astype(float)
        y = np.take(form.data, labels[y_label], axis=attr_axis).astype(float)

        c = None
        if color_label is not None:
            c = np.take(
                form.data, labels[color_label], axis=attr_axis
            ).astype(float)

        valid = np.isfinite(x) & np.isfinite(y)
        if c is not None:
            valid &= np.isfinite(c)
        n_points = int(valid.sum())
        if n_points == 0:
            raise StepError(
                f"scatter: no finite points to plot "
                f"(x={x_label}, y={y_label})"
            )
        x = x[valid]
        y = y[valid]
        if c is not None:
            c = c[valid]

        fig, ax = plt.subplots(figsize=(5, 4.5))

        if c is None:
            ax.scatter(
                x, y, s=point_size, alpha=alpha,
                edgecolors="none", rasterized=True,
            )
        else:
            unique = np.unique(c)
            if len(unique) <= 20:
                for u in unique:
                    mask = c == u
                    label = (
                        str(int(u)) if float(u).is_integer() else str(u)
                    )
                    ax.scatter(
                        x[mask], y[mask], s=point_size, alpha=alpha,
                        edgecolors="none", rasterized=True, label=label,
                    )
                ax.legend(frameon=False, markerscale=1.5)
            else:
                sc = ax.scatter(
                    x, y, c=c, s=point_size, alpha=alpha,
                    cmap="viridis", edgecolors="none", rasterized=True,
                )
                fig.colorbar(sc, ax=ax, label=color_label)

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "scatter",
            "filename": filename,
            "path": out_path,
            "x_label": x_label,
            "y_label": y_label,
            "color_label": color_label,
            "n_points": n_points,
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_points": n_points,
            "path": out_path,
        }

        print(f"[scatter] {n_points} points -> {out_path}")

    def export(self, ctx: Context) -> dict:
        return self._export_data