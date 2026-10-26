# src/task/step/steps/forest_plot.py
"""Forest plot of hazard ratios from a Cox regression result.

Input is the 2D form produced by ``cox_regression``: one row per
covariate, one column per statistic. The operator draws a horizontal
forest plot with one line per covariate, showing the point estimate
of HR and its 95% confidence interval.

The reference line is HR = 1 (log scale). Covariates whose CI does
not cross the reference line are highlighted.

Params:
    dim         : covariate dim (default "covariate")
    stat_dim    : statistic dim (default "statistic")
    hr_label    : column with HR (default "HR")
    low_label   : column with lower CI (default "CI_low")
    high_label  : column with upper CI (default "CI_high")
    p_label     : column with p-value (default "P")
    filename    : output file name (required)
    title       : optional plot title
    xlabel      : optional x-label (default "Hazard ratio (95% CI)")
    xlim        : optional [x_min, x_max] on the HR scale
    log_scale   : use log scale on x (default True)
    color_sig   : color for significant rows (default "#D62728")
    color_ns    : color for non-significant rows (default "#4C72B0")
    sort_by    : "input" | "hr" | "p" (default "input")
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.contracts import port, param
from src.core.forms.metadata import project_metadata
from src.task.step.steps._plot_helpers import save_figure, setup_style


class ForestPlotStep(Step):
    """Draw a forest plot of hazard ratios."""
    parameters_schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
     'type': 'object',
     'properties': {'dim': {'title': '分析维度', 'type': 'string', 'default': 'covariate'},
                    'stat_dim': {'title': '统计量维度', 'type': 'string', 'default': 'statistic'},
                    'hr_label': {'title': 'HR 字段', 'type': 'string', 'default': 'HR'},
                    'low_label': {'title': 'CI 下界字段', 'type': 'string', 'default': 'CI_low'},
                    'high_label': {'title': 'CI 上界字段', 'type': 'string', 'default': 'CI_high'},
                    'p_label': {'title': 'P / Q 字段', 'type': 'string', 'default': 'P'},
                    'filename': {'title': '图片文件名', 'type': 'string', 'x-ui-default': 'forest_plot.png'},
                    'title': {'title': '图标题', 'type': 'string'},
                    'xlabel': {'title': 'X 轴标题', 'type': 'string', 'default': 'Hazard ratio (95% CI)'},
                    'xlim': {'title': 'X 轴范围', 'type': ['object', 'array']},
                    'color_sig': {'title': 'color_sig', 'type': 'string', 'default': '#D62728'},
                    'color_ns': {'title': 'color_ns', 'type': 'string', 'default': '#4C72B0'},
                    'sort_by': {'title': '排序', 'enum': ['input', 'hr', 'p'], 'default': 'input'},
                    'log_scale': {'title': 'Log 坐标', 'type': 'boolean', 'default': True}},
     'additionalProperties': True,
     'required': ['filename']}
    title = 'Forest plot'
    category = '可视化'
    icon = 'ChartLine'
    description = 'HR 与置信区间'
    preview = {'kind': 'forest', 'caption': '效应估计与置信区间'}

    name = "forest_plot"
    inputs_arity = 1
    outputs = []
    input_contracts = [port(ndim=2, dims=[param("dim", "covariate"), param("stat_dim", "statistic")], labels=[{"dim": param("stat_dim", "statistic"), "values": [param("hr_label", "HR"), param("low_label", "CI_low"), param("high_label", "CI_high"), param("p_label", "P")]}])]
    output_contract = {"mode": "none"}

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        form = inputs[0]
        dim = ctx.step_params.get("dim", "covariate")
        stat_dim = ctx.step_params.get("stat_dim", "statistic")
        hr_label = ctx.step_params.get("hr_label", "HR")
        low_label = ctx.step_params.get("low_label", "CI_low")
        high_label = ctx.step_params.get("high_label", "CI_high")
        p_label = ctx.step_params.get("p_label", "P")
        filename = ctx.step_params.get("filename")
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get(
            "xlabel", "Hazard ratio (95% CI)"
        )
        xlim = ctx.step_params.get("xlim")
        log_scale = bool(ctx.step_params.get("log_scale", True))
        color_sig = ctx.step_params.get("color_sig", "#D62728")
        color_ns = ctx.step_params.get("color_ns", "#4C72B0")
        sort_by = ctx.step_params.get("sort_by", "input")

        if not filename:
            raise StepError("forest_plot: 'filename' is required")
        if form.data.ndim != 2:
            raise StepError(
                f"forest_plot: input must be 2D, got ndim={form.data.ndim}"
            )
        for d, name in ((dim, "dim"), (stat_dim, "stat_dim")):
            if d not in form.dims:
                raise StepError(
                    f"forest_plot: {name} '{d}' not present. "
                    f"Available: {form.dims}"
                )
        if sort_by not in ("input", "hr", "p"):
            raise StepError(
                f"forest_plot: sort_by must be 'input', 'hr' or 'p', "
                f"got {sort_by!r}"
            )

        cov_axis = form.dims.index(dim)
        stat_axis = form.dims.index(stat_dim)
        stat_labels = form.labels.get(stat_dim, {})

        for lbl, name in (
            (hr_label, "hr_label"),
            (low_label, "low_label"),
            (high_label, "high_label"),
        ):
            if lbl not in stat_labels:
                raise StepError(
                    f"forest_plot: {name}='{lbl}' not in dim "
                    f"'{stat_dim}'. Available: {sorted(stat_labels)}"
                )

        has_p = p_label in stat_labels

        hr = np.take(
            form.data, stat_labels[hr_label], axis=stat_axis
        ).astype(float)
        low = np.take(
            form.data, stat_labels[low_label], axis=stat_axis
        ).astype(float)
        high = np.take(
            form.data, stat_labels[high_label], axis=stat_axis
        ).astype(float)
        p = (
            np.take(form.data, stat_labels[p_label], axis=stat_axis)
            .astype(float)
            if has_p else np.full(hr.shape, np.nan)
        )

        cov_labels = form.labels.get(dim, {})
        pos_to_label = {v: k for k, v in cov_labels.items()}
        names = [
            pos_to_label.get(i, f"#{i}") for i in range(hr.shape[0])
        ]

        valid = (
            np.isfinite(hr)
            & np.isfinite(low)
            & np.isfinite(high)
            & (low > 0)
            & (high > 0)
        )
        n_total = int(hr.size)
        n_valid = int(valid.sum())
        if n_valid == 0:
            raise StepError(
                "forest_plot: no rows with finite HR and CI"
            )

        rows = [
            (names[i], hr[i], low[i], high[i], p[i])
            for i in range(hr.shape[0]) if valid[i]
        ]

        if sort_by == "hr":
            rows.sort(key=lambda r: r[1])
        elif sort_by == "p":
            rows.sort(key=lambda r: (
                r[4] if np.isfinite(r[4]) else 1.0
            ))

        display_names = [r[0] for r in rows]
        hr_v = np.array([r[1] for r in rows])
        low_v = np.array([r[2] for r in rows])
        high_v = np.array([r[3] for r in rows])
        p_v = np.array([r[4] for r in rows])

        if has_p:
            sig_mask = p_v < 0.05
        else:
            sig_mask = (low_v > 1.0) | (high_v < 1.0)

        n_sig = int(sig_mask.sum())
        n_ns = int((~sig_mask).sum())

        y_pos = np.arange(len(rows))[::-1]

        fig, ax = plt.subplots(
            figsize=(5.5, max(2.5, 0.35 * len(rows) + 1.5))
        )

        colors = np.where(sig_mask, color_sig, color_ns)

        for i, y in enumerate(y_pos):
            ax.plot(
                [low_v[i], high_v[i]], [y, y],
                color=colors[i], lw=1.4, solid_capstyle="butt",
            )
            ax.scatter(
                [hr_v[i]], [y], color=colors[i],
                s=30, zorder=3, edgecolors="white",
                linewidths=0.6,
            )

        ax.axvline(
            1.0, color="black", lw=0.8, ls="--", alpha=0.6,
        )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(display_names, fontsize=8)
        ax.set_xlabel(xlabel)
        if log_scale:
            ax.set_xscale("log")
        if xlim is not None:
            if (not isinstance(xlim, list) or len(xlim) != 2
                    or xlim[0] >= xlim[1]):
                raise StepError(
                    f"forest_plot: xlim must be [min, max], got {xlim}"
                )
            ax.set_xlim(xlim[0], xlim[1])
        if title:
            ax.set_title(title)

        # Right-side annotation: HR (CI) and P
        x_right = ax.get_xlim()[1]
        for i, y in enumerate(y_pos):
            p_str = (
                f"P={p_v[i]:.3g}" if np.isfinite(p_v[i]) else ""
            )
            txt = (
                f"{hr_v[i]:.2f} "
                f"({low_v[i]:.2f}–{high_v[i]:.2f})"
            )
            if p_str:
                txt += f"  {p_str}"
            ax.text(
                x_right * 1.02, y, txt,
                va="center", ha="left", fontsize=7,
                transform=ax.get_yaxis_transform()
                if False else ax.transData,
            )

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "forest_plot",
            "filename": filename,
            "path": out_path,
            "dim": dim,
            "stat_dim": stat_dim,
            "hr_label": hr_label,
            "low_label": low_label,
            "high_label": high_label,
            "p_label": p_label if has_p else None,
            "sort_by": sort_by,
            "log_scale": log_scale,
            "n_total": n_total,
            "n_valid": n_valid,
            "n_significant": n_sig,
            "n_ns": n_ns,
            "rows": [
                {
                    "covariate": display_names[i],
                    "HR": float(hr_v[i]),
                    "CI_low": float(low_v[i]),
                    "CI_high": float(high_v[i]),
                    "P": float(p_v[i]) if np.isfinite(p_v[i])
                    else None,
                    "significant": bool(sig_mask[i]),
                }
                for i in range(len(rows))
            ],
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_valid": n_valid,
            "n_significant": n_sig,
            "path": out_path,
        }

        print(
            f"[forest_plot] {n_valid} covariates, "
            f"{n_sig} significant -> {out_path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data