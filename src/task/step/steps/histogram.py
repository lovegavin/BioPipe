# src/task/step/steps/histogram.py
"""Histogram operator.

Input is a single 2D form. One dimension of the form holds the
attributes (columns); the other dimension holds the observations.

The operator reads one labeled column and plots its distribution.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._plot_helpers import save_figure, setup_style


class HistogramStep(Step):
    """Draw a histogram.

    Params:
        dim         : attribute dimension (default "feature")
        value_label : column label for the values
        bins        : number of bins (default 40)
        filename    : output file name
        title       : optional plot title
        xlabel      : optional x-axis label (default: value_label)
        ylabel      : optional y-axis label (default: "Count")
        log_y       : use log scale on the y axis (default False)
    """

    name = "histogram"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        form = inputs[0]
        dim = ctx.step_params.get("dim", "feature")
        value_label = ctx.step_params["value_label"]
        bins = int(ctx.step_params.get("bins", 40))
        filename = ctx.step_params["filename"]
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get("xlabel", value_label)
        ylabel = ctx.step_params.get("ylabel", "Count")
        log_y = bool(ctx.step_params.get("log_y", False))

        if form.data.ndim != 2:
            raise StepError(
                f"histogram requires a 2D form, got ndim={form.data.ndim}"
            )
        if dim not in form.dims:
            raise StepError(
                f"Dim '{dim}' not present. Available: {form.dims}"
            )

        attr_axis = form.dims.index(dim)
        labels = form.labels[dim]
        if value_label not in labels:
            raise StepError(
                f"histogram: value_label='{value_label}' not in dim "
                f"'{dim}'. Available: {sorted(labels)}"
            )

        values = np.take(
            form.data, labels[value_label], axis=attr_axis
        ).astype(float)
        finite = values[np.isfinite(values)]
        n_valid = int(finite.size)
        if n_valid == 0:
            raise StepError(
                f"histogram: no finite values in '{value_label}'"
            )

        fig, ax = plt.subplots(figsize=(4.5, 3.5))
        ax.hist(
            finite, bins=bins, color="#0072B2",
            edgecolor="white", linewidth=0.4,
        )
        if log_y:
            ax.set_yscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "histogram",
            "filename": filename,
            "path": out_path,
            "value_label": value_label,
            "bins": bins,
            "n_valid": n_valid,
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
            "mean": float(np.mean(finite)),
            "std": float(np.std(finite)),
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_valid": n_valid,
            "path": out_path,
        }

        print(f"[histogram] {n_valid} values -> {out_path}")

    def export(self, ctx: Context) -> dict:
        return self._export_data