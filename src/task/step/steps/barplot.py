# src/task/step/steps/barplot.py
"""Stacked bar plot of a matrix along one axis.

Input is a 2D form. One axis is the "composition" axis (features
that will be stacked) and the other is the "sample" axis (bars).
For each sample, one bar is drawn, and the features are stacked in
their order along the composition axis.

This is the standard visualization for compositional data:
relative abundance of taxa per sample, cell-type fractions per
sample, isoform fractions, etc.

Layout
------
    input  dims: [<composition_dim>, <sample_dim>]  (any orientation)
    output      : a barplot image

Feature selection
-----------------
The operator can show only the top N most abundant features. The
remaining features are summed into a single "Other" category.

Normalization
-------------
``normalize=True`` (default) divides each sample by its total, so
each bar sums to 1. This is the correct default for compositional
data. Set to False to plot raw values.

Params:
    dim          : composition dim (required)
    sample_dim   : sample dim (required)
    top_n        : show only the top N most abundant features
                   (default 20; use 0 or None to show all)
    other_label  : label for the aggregated remainder
                   (default "Other")
    normalize    : divide each sample by its total (default True)
    filename     : output file name (required)
    title        : optional plot title
    xlabel       : optional x label (default: sample_dim)
    ylabel       : optional y label (default: "Fraction" or "Value")
    cmap         : matplotlib colormap (default "tab20")
    figsize      : [width, height] in inches (default auto)
    legend       : show a legend (default True)
    legend_ncol  : number of columns in the legend (default 3)
    rotate_labels: rotate x tick labels 90 degrees (default True)
"""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._microbiome import CONTRACTS, SCHEMAS, estimate
from src.task.step.steps._plot_helpers import save_figure, setup_style


class BarplotStep(Step):
    """Stacked bar plot of a matrix along one axis."""

    name = "barplot"
    inputs_arity = 1
    outputs = []
    title = 'Composition barplot'
    category = "Microbiome"
    builtin_package = "biopipe-microbiome"
    legacy_parameters = False
    parameters_schema = SCHEMAS['barplot']
    input_contracts, output_contract = CONTRACTS['barplot']

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt
        from matplotlib import colormaps

        setup_style()

        form = inputs[0]
        dim = ctx.step_params.get("dim")
        sample_dim = ctx.step_params.get("sample_dim")
        top_n = ctx.step_params.get("top_n", 20)
        other_label = ctx.step_params.get("other_label", "Other")
        normalize = bool(ctx.step_params.get("normalize", True))
        filename = ctx.step_params.get("filename")
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get("xlabel", sample_dim)
        ylabel = ctx.step_params.get(
            "ylabel", "Fraction" if normalize else "Value"
        )
        cmap_name = ctx.step_params.get("cmap", "tab20")
        figsize = ctx.step_params.get("figsize")
        legend = bool(ctx.step_params.get("legend", True))
        legend_ncol = int(ctx.step_params.get("legend_ncol", 3))
        rotate_labels = bool(
            ctx.step_params.get("rotate_labels", True)
        )

        for name, v in (
            ("dim", dim),
            ("sample_dim", sample_dim),
            ("filename", filename),
        ):
            if not v:
                raise StepError(f"barplot: '{name}' is required")
        if form.data.ndim != 2:
            raise StepError(
                f"barplot: input must be 2D, got ndim={form.data.ndim}"
            )
        for d, name in ((dim, "dim"),
                        (sample_dim, "sample_dim")):
            if d not in form.dims:
                raise StepError(
                    f"barplot: {name} '{d}' not present. "
                    f"Available: {form.dims}"
                )
        if dim == sample_dim:
            raise StepError(
                f"barplot: dim and sample_dim are both '{dim}'"
            )
        if top_n is not None:
            top_n = int(top_n)
            if top_n < 0:
                raise StepError(
                    f"barplot: top_n must be >= 0, got {top_n}"
                )

        # Orient matrix so rows = features, columns = samples.
        feat_axis = form.dims.index(dim)
        sample_axis = form.dims.index(sample_dim)
        matrix = np.moveaxis(
            form.data, (feat_axis, sample_axis), (0, 1)
        ).astype(np.float64)

        n_features, n_samples = matrix.shape
        if n_features == 0 or n_samples == 0:
            raise StepError("barplot: input matrix is empty")

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(matrix)
        else:
            missing = matrix == missing_code
        matrix = np.where(missing, 0.0, matrix)
        # Negative values are not meaningful for a stacked plot.
        if (matrix < 0).any():
            raise StepError(
                "barplot: matrix contains negative values"
            )

        if normalize:
            totals = matrix.sum(axis=0, keepdims=True)
            with np.errstate(invalid="ignore", divide="ignore"):
                matrix = np.where(
                    totals > 0, matrix / totals, 0.0
                )

        # Feature labels (on the feature axis).
        feat_labels_map = form.labels[dim]
        pos_to_feat = {v: k for k, v in feat_labels_map.items()}
        feat_names = [
            pos_to_feat.get(i, f"#{i}") for i in range(n_features)
        ]

        # Sample labels (on the sample axis).
        sample_labels_map = form.labels[sample_dim]
        pos_to_sample = {v: k for k, v in sample_labels_map.items()}
        sample_names = [
            pos_to_sample.get(i, f"#{i}") for i in range(n_samples)
        ]

        # Select top_n features by their total abundance.
        feature_totals = matrix.sum(axis=1)
        if top_n is not None and 0 < top_n < n_features:
            order = np.argsort(feature_totals)[::-1]
            selected_idx = order[:top_n]
            other_idx = order[top_n:]
        else:
            selected_idx = np.arange(n_features)
            other_idx = np.array([], dtype=int)

        selected_names = [feat_names[i] for i in selected_idx]
        selected_matrix = matrix[selected_idx, :]

        if other_idx.size:
            other_block = matrix[other_idx, :].sum(axis=0)
            selected_matrix = np.vstack(
                [selected_matrix, other_block.reshape(1, -1)]
            )
            selected_names = selected_names + [other_label]

        n_stacks = selected_matrix.shape[0]

        # Draw stacked bars.
        figsize_auto = (
            max(6.0, 0.3 * n_samples + 2),
            max(4.0, 0.1 * n_stacks + 3),
        )
        if figsize is None:
            figsize = figsize_auto

        fig, ax = plt.subplots(figsize=tuple(figsize))

        x = np.arange(n_samples)
        bottoms = np.zeros(n_samples, dtype=np.float64)

        cmap = colormaps.get_cmap(cmap_name)
        colors = [cmap(i % cmap.N) for i in range(n_stacks)]

        for i in range(n_stacks):
            values = selected_matrix[i]
            ax.bar(
                x, values, bottom=bottoms, width=0.85,
                color=colors[i], edgecolor="none",
                label=selected_names[i],
            )
            bottoms += values

        ax.set_xticks(x)
        if rotate_labels:
            ax.set_xticklabels(
                sample_names, rotation=90, fontsize=7
            )
        else:
            ax.set_xticklabels(sample_names, fontsize=7)
        ax.set_xlim(-0.5, n_samples - 0.5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if normalize:
            ax.set_ylim(0, 1)
        if title:
            ax.set_title(title)

        if legend:
            ax.legend(
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False,
                fontsize=7,
                ncol=legend_ncol,
            )

        out_path = save_figure(fig, ctx, filename)

        per_sample = {}
        for j, sname in enumerate(sample_names):
            if normalize:
                totals = selected_matrix[:, j].sum()
                if totals > 0:
                    fractions = selected_matrix[:, j] / totals
                else:
                    fractions = np.zeros(n_stacks)
            else:
                fractions = selected_matrix[:, j]
            per_sample[sname] = {
                selected_names[i]: float(fractions[i])
                for i in range(n_stacks)
            }

        self._export_data = {
            "kind": "barplot",
            "filename": filename,
            "path": out_path,
            "dim": dim,
            "sample_dim": sample_dim,
            "normalize": normalize,
            "n_features_shown": n_stacks,
            "n_features_original": n_features,
            "n_samples": n_samples,
            "top_n": top_n,
            "other_label": other_label if other_idx.size else None,
            "feature_order": selected_names,
            "samples": sample_names,
            "per_sample": per_sample,
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_features_shown": n_stacks,
            "n_samples": n_samples,
            "path": out_path,
        }

        print(
            f"[barplot] {n_samples} samples x {n_stacks} "
            f"features{' (top_n=' + str(top_n) + ')' if top_n else ''}"
            f" -> {out_path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data