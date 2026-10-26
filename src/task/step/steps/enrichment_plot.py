# src/task/step/steps/enrichment_plot.py
"""Horizontal bar plot of a GO enrichment result.

Draws the top N terms from an ``enrich_go`` output as horizontal
bars of ``-log10(Q)``, with bar color encoded by ``n_hit``. This is
the standard summary figure for over-representation analysis.

Layout
------
    input   dims: [<term_dim>, "statistic"]
    output  no Form; PNG written to the run figures directory

The term axis and the statistic axis are detected from the input
dims. ``Q_VALUE`` and ``n_hit`` must be present on the statistic
axis, either from ``enrich_go`` or from an equivalent upstream.

Params:
    term_dim      : name of the term dimension (auto-detected)
    statistic_dim : name of the statistic dimension (default "statistic")
    q_column      : column holding the adjusted p-value (default "Q_VALUE")
    size_column   : column driving bar color (default "n_hit")
    top_n         : number of terms to plot, ranked by Q (default 20)
    filename      : PNG filename inside the figures directory
    title         : plot title
"""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import port
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._plot_helpers import setup_style, save_figure


class EnrichmentPlotStep(Step):
    """Horizontal bar plot of enrichment results."""
    title = 'enrichment_plot'
    description = 'Horizontal bar plot of enrichment results.'

    name = "enrichment_plot"
    category = "visualization"
    icon = "ChartBar"
    inputs_arity = 1
    outputs = []
    input_contracts = [port(ndim=2)]
    output_contract = {"mode": "report"}
    parameters_schema = {
        "type": "object",
        "properties": {
            "term_dim": {
                "type": "string",
                "title": "Term dimension",
            },
            "statistic_dim": {
                "type": "string",
                "title": "Statistic dimension",
                "default": "statistic",
            },
            "q_column": {
                "type": "string",
                "title": "Q-value column",
                "default": "Q_VALUE",
            },
            "size_column": {
                "type": "string",
                "title": "Color column",
                "default": "n_hit",
            },
            "top_n": {
                "type": "integer",
                "title": "Top N terms",
                "minimum": 1,
                "default": 20,
            },
            "filename": {
                "type": "string",
                "title": "Output filename",
                "default": "enrichment.png",
            },
            "title": {
                "type": "string",
                "title": "Plot title",
            },
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        statistic_dim = ctx.step_params.get("statistic_dim", "statistic")
        term_dim = ctx.step_params.get("term_dim")
        q_column = ctx.step_params.get("q_column", "Q_VALUE")
        size_column = ctx.step_params.get("size_column", "n_hit")
        top_n = int(ctx.step_params.get("top_n", 20))
        filename = ctx.step_params.get("filename", "enrichment.png")
        title = ctx.step_params.get("title")

        if form.data.ndim != 2:
            raise StepError(
                f"enrichment_plot: input must be 2D, "
                f"got ndim={form.data.ndim}"
            )
        if statistic_dim not in form.dims:
            raise StepError(
                f"enrichment_plot: statistic_dim '{statistic_dim}' not "
                f"in {form.dims}"
            )
        if term_dim is None:
            candidates = [d for d in form.dims if d != statistic_dim]
            if len(candidates) != 1:
                raise StepError(
                    f"enrichment_plot: cannot infer term_dim from "
                    f"{form.dims}; specify 'term_dim'"
                )
            term_dim = candidates[0]
        if term_dim not in form.dims:
            raise StepError(
                f"enrichment_plot: term_dim '{term_dim}' not in "
                f"{form.dims}"
            )

        stat_labels = form.labels.get(statistic_dim, {})
        for col in (q_column, size_column):
            if col not in stat_labels:
                raise StepError(
                    f"enrichment_plot: column '{col}' not in "
                    f"statistic labels {sorted(stat_labels)}"
                )

        if top_n < 1:
            raise StepError(
                f"enrichment_plot: top_n must be >= 1, got {top_n}"
            )

        if form.dims.index(term_dim) == 0:
            data = form.data
        else:
            data = form.data.T

        q_values = data[:, stat_labels[q_column]].astype(np.float64)
        sizes = data[:, stat_labels[size_column]].astype(np.float64)

        pos_to_term = {v: k for k, v in form.labels[term_dim].items()}
        n_terms = data.shape[0]
        term_names = [pos_to_term[i] for i in range(n_terms)]

        finite = np.isfinite(q_values)
        if not finite.any():
            raise StepError(
                "enrichment_plot: no finite Q values to plot"
            )

        finite_q = q_values.copy()
        finite_q[~finite] = 1.0
        order = np.argsort(finite_q, kind="stable")
        kept = order[:top_n]

        kept_q = q_values[kept]
        kept_sizes = sizes[kept]
        kept_names = [term_names[int(i)] for i in kept]

        neg_log_q = -np.log10(np.clip(kept_q, 1e-300, 1.0))

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.cm import ScalarMappable
        from matplotlib.colors import Normalize

        setup_style()

        height = max(3.0, 0.4 * len(kept_names) + 1.0)
        fig, ax = plt.subplots(figsize=(8, height))

        y = np.arange(len(kept_names))
        if kept_sizes.max() > kept_sizes.min():
            norm = Normalize(vmin=kept_sizes.min(), vmax=kept_sizes.max())
        else:
            norm = Normalize(vmin=0, vmax=1)
        cmap = plt.cm.viridis

        colors = cmap(norm(kept_sizes))
        ax.barh(y, neg_log_q, color=colors, edgecolor="black",
                linewidth=0.4)

        ax.set_yticks(y)
        ax.set_yticklabels(kept_names, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel("-log10(Q)")
        if title:
            ax.set_title(title)

        sm = ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, shrink=0.6)
        cbar.set_label(size_column)

        path = save_figure(fig, ctx, filename)

        self._export_data = {
            "term_dim": term_dim,
            "statistic_dim": statistic_dim,
            "q_column": q_column,
            "size_column": size_column,
            "top_n": top_n,
            "n_plotted": len(kept_names),
            "figure_path": path,
            "plotted_terms": [
                {
                    "term": kept_names[i],
                    "Q_VALUE": float(kept_q[i]),
                    "neg_log10_Q": float(neg_log_q[i]),
                    size_column: float(kept_sizes[i]),
                }
                for i in range(len(kept_names))
            ],
        }

        ctx.metadata.setdefault(self.name, {})[path] = {
            "n_plotted": len(kept_names),
        }

        print(
            f"[enrichment_plot] plotted {len(kept_names)} terms "
            f"-> {path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
