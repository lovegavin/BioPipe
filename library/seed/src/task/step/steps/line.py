# src/task/step/steps/line.py
"""Line plot operator.

Input is a single 2D form. One dimension holds the attributes
(columns); the other holds the observations. The operator reads two
labeled columns as x and y, sorts by x, and draws a line.
"""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._plot_helpers import save_figure, setup_style, figure_report


class LineStep(Step):
    """Draw a line plot.

    Params:
        dim      : attribute dimension (default "feature")
        x_label  : column label for the x axis
        y_label  : column label for the y axis
        filename : output file name
        title    : optional plot title
        xlabel   : optional x-axis label (default: x_label)
        ylabel   : optional y-axis label (default: y_label)
        sort     : sort points by x before drawing (default True)
    """
    provider = 'biopipe-plots'
    parameters_file = 'line.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'line',
     'version': '1.0.0',
     'kind': 'operator',
     'title': '折线图',
     'description': '选择两个数值标签，按横坐标排序后绘制曲线。',
     'category': '可视化',
     'icon': 'ChartLine',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': 'feature'}],
                               'labels': [{'dim': {'param': 'dim', 'default': 'feature'},
                                           'values': [{'param': 'x_label', 'default': None},
                                                      {'param': 'y_label', 'default': None}]}],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'report'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': None,
     'preview': {'kind': 'line', 'caption': '随序列变化的趋势'}}




    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style(ctx)

        form = inputs[0]
        dim = ctx.step_params.get("dim", "feature")
        x_label = ctx.step_params["x_label"]
        y_label = ctx.step_params["y_label"]
        filename = ctx.step_params["filename"]
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get("xlabel", x_label)
        ylabel = ctx.step_params.get("ylabel", y_label)
        do_sort = bool(ctx.step_params.get("sort", True))

        if form.data.ndim != 2:
            raise StepError(
                f"line requires a 2D form, got ndim={form.data.ndim}"
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
                    f"line: {name}='{lbl}' not in dim '{dim}'. "
                    f"Available: {sorted(labels)}"
                )

        x = np.take(form.data, labels[x_label], axis=attr_axis).astype(float)
        y = np.take(form.data, labels[y_label], axis=attr_axis).astype(float)

        valid = np.isfinite(x) & np.isfinite(y)
        n_points = int(valid.sum())
        if n_points == 0:
            raise StepError(
                f"line: no finite points to plot "
                f"(x={x_label}, y={y_label})"
            )
        x = x[valid]
        y = y[valid]

        if do_sort:
            order = np.argsort(x)
            x = x[order]
            y = y[order]

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(x, y, color="#0072B2", lw=1.0)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "line",
            "filename": filename,
            "path": out_path,
            "x_label": x_label,
            "y_label": y_label,
            "n_points": n_points,
            "sorted": do_sort,
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_points": n_points,
            "path": out_path,
        }

        print(f"[line] {n_points} points -> {out_path}")

    def export(self, ctx: Context) -> dict:
        return figure_report(self._export_data)