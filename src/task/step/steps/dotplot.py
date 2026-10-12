# src/task/step/steps/dotplot.py
"""Dot plot of feature values grouped by a label column.

Two inputs share a sample dim. The first carries per-feature values
across samples; the second carries group labels. For each (group,
feature) cell the operator computes two statistics:

    value       mean (or median, or sum) of the feature within
                the group
    proportion  fraction of samples in the group whose value passes
                the "expressed" rule (non-zero by default)

The result is drawn as a grid: x = features, y = groups, dot color
= value, dot size = proportion. This is the standard marker dot
plot in single-cell analysis, but it works on any two-form dataset
with a grouping column.

The same two statistics are exported as a table so the numbers are
auditable.

Params:
    feature_dim     : feature dim on the data form (required)
    group_dim       : sample dim shared by both forms (required)
    features        : list of feature labels to show (required)
    group_label     : column on the metadata's other dim (required)
    groups          : optional list of groups to show, in order
    statistic       : "mean" | "median" | "sum" (default "mean")
    proportion_mode : "nonzero" | "threshold" (default "nonzero")
    threshold       : value used when proportion_mode="threshold"
    filename        : output file name (required)
    title           : optional plot title
    xlabel          : optional x label (default: feature_dim)
    ylabel          : optional y label (default: group_label)
    cmap            : matplotlib colormap (default "viridis")
    dot_scale       : max dot size in points^2 (default 200)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._plot_helpers import save_figure, setup_style


_STATS = ("mean", "median", "sum")
_PROP_MODES = ("nonzero", "threshold")


class DotplotStep(Step):
    """Dot plot of features grouped by a label column."""

    name = "dotplot"
    inputs_arity = 2
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        data_form, meta_form = inputs
        feature_dim = ctx.step_params.get("feature_dim")
        group_dim = ctx.step_params.get("group_dim")
        features = ctx.step_params.get("features")
        group_label = ctx.step_params.get("group_label")
        groups_arg = ctx.step_params.get("groups")
        statistic = ctx.step_params.get("statistic", "mean")
        proportion_mode = ctx.step_params.get(
            "proportion_mode", "nonzero"
        )
        threshold = float(ctx.step_params.get("threshold", 0.0))
        filename = ctx.step_params.get("filename")
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get("xlabel", feature_dim)
        ylabel = ctx.step_params.get("ylabel", group_label)
        cmap = ctx.step_params.get("cmap", "viridis")
        dot_scale = float(ctx.step_params.get("dot_scale", 200))

        for name, v in (
            ("feature_dim", feature_dim),
            ("group_dim", group_dim),
            ("features", features),
            ("group_label", group_label),
            ("filename", filename),
        ):
            if not v:
                raise StepError(f"dotplot: '{name}' is required")
        if not isinstance(features, list) or not features:
            raise StepError(
                "dotplot: 'features' must be a non-empty list"
            )
        if statistic not in _STATS:
            raise StepError(
                f"dotplot: statistic must be one of {list(_STATS)}, "
                f"got {statistic!r}"
            )
        if proportion_mode not in _PROP_MODES:
            raise StepError(
                f"dotplot: proportion_mode must be one of "
                f"{list(_PROP_MODES)}, got {proportion_mode!r}"
            )
        if data_form.data.ndim != 2:
            raise StepError(
                f"dotplot: data form must be 2D, "
                f"got ndim={data_form.data.ndim}"
            )
        for d, name in ((feature_dim, "feature_dim"),
                        (group_dim, "group_dim")):
            if d not in data_form.dims:
                raise StepError(
                    f"dotplot: {name} '{d}' not in data form. "
                    f"Available: {data_form.dims}"
                )
        if feature_dim == group_dim:
            raise StepError(
                f"dotplot: feature_dim and group_dim are both "
                f"'{feature_dim}'"
            )
        if group_dim not in meta_form.dims:
            raise StepError(
                f"dotplot: group_dim '{group_dim}' not in metadata. "
                f"Available: {meta_form.dims}"
            )

        # Align samples.
        data_group_labels = data_form.labels[group_dim]
        meta_group_labels = meta_form.labels[group_dim]
        common = [
            s for s in data_group_labels if s in meta_group_labels
        ]
        if len(common) < 2:
            raise StepError(
                f"dotplot: only {len(common)} common samples on "
                f"'{group_dim}'."
            )
        data_idx = [data_group_labels[s] for s in common]
        meta_idx = [meta_group_labels[s] for s in common]

        data_axis = data_form.dims.index(group_dim)
        meta_axis = meta_form.dims.index(group_dim)
        data_sub = np.take(data_form.data, data_idx, axis=data_axis)
        meta_sub = np.take(meta_form.data, meta_idx, axis=meta_axis)

        # Resolve the group column.
        other_dims = [d for d in meta_form.dims if d != group_dim]
        if len(other_dims) != 1:
            raise StepError(
                f"dotplot: metadata must be 2D with '{group_dim}' "
                f"and one other dim, got {meta_form.dims}"
            )
        other = other_dims[0]
        if group_label not in meta_form.labels.get(other, {}):
            raise StepError(
                f"dotplot: group_label '{group_label}' not in dim "
                f"'{other}'. Available: "
                f"{sorted(meta_form.labels.get(other, {}))}"
            )
        group_pos = meta_form.labels[other][group_label]
        group_axis_meta = meta_form.dims.index(other)
        group_codes = np.take(meta_sub, group_pos, axis=group_axis_meta)

        encoders = meta_form.info.get("encoders", {})
        encoder = None
        if other in encoders and group_label in encoders[other]:
            encoder = encoders[other][group_label]

        # Resolve each feature's position on the data form.
        data_feature_labels = data_form.labels[feature_dim]
        missing = [f for f in features if f not in data_feature_labels]
        if missing:
            raise StepError(
                f"dotplot: features not found in '{feature_dim}': "
                f"{missing[:5]}. Available: "
                f"{sorted(data_feature_labels)[:5]}..."
            )

        feat_axis = data_form.dims.index(feature_dim)
        feature_positions = [
            data_feature_labels[f] for f in features
        ]

        # Extract values per feature and group.
        # data_sub is [..., feature, ..., sample, ...] in the original
        # 2D orientation; we handle both orderings.
        n_samples = len(common)
        # Build a sample -> group name list.
        sample_groups = [
            _decode(group_codes[i], encoder) for i in range(n_samples)
        ]
        valid_sample = np.array(
            [g is not None for g in sample_groups]
        )

        # Collect group set.
        all_groups = sorted({
            g for g in sample_groups if g is not None
        })
        if groups_arg is not None:
            if not isinstance(groups_arg, list) or not groups_arg:
                raise StepError(
                    "dotplot: 'groups' must be a non-empty list"
                )
            groups_arg = [str(g) for g in groups_arg]
            missing_g = [g for g in groups_arg if g not in all_groups]
            if missing_g:
                raise StepError(
                    f"dotplot: groups not found: {missing_g}. "
                    f"Available: {all_groups}"
                )
            group_order = list(groups_arg)
        else:
            group_order = all_groups
        if not group_order:
            raise StepError(
                "dotplot: no groups with valid samples"
            )

        # Compute per-cell statistics.
        n_features = len(features)
        n_groups = len(group_order)
        value_matrix = np.full((n_groups, n_features), np.nan)
        prop_matrix = np.full((n_groups, n_features), np.nan)

        for gi, g in enumerate(group_order):
            g_mask = np.array(
                [sg == g for sg in sample_groups]
            )
            if not g_mask.any():
                continue
            for fi, fpos in enumerate(feature_positions):
                values = np.take(
                    data_sub, fpos, axis=feat_axis
                ).astype(float)[g_mask]
                values = values[np.isfinite(values)]
                if values.size == 0:
                    continue
                if statistic == "mean":
                    value_matrix[gi, fi] = float(values.mean())
                elif statistic == "median":
                    value_matrix[gi, fi] = float(np.median(values))
                else:
                    value_matrix[gi, fi] = float(values.sum())

                if proportion_mode == "nonzero":
                    prop_matrix[gi, fi] = float((values != 0).mean())
                else:
                    prop_matrix[gi, fi] = float(
                        (values >= threshold).mean()
                    )

        # Plot.
        fig, ax = plt.subplots(
            figsize=(
                max(3.5, 0.5 * n_features + 2),
                max(3.0, 0.4 * n_groups + 1.5),
            )
        )

        finite_vals = value_matrix[np.isfinite(value_matrix)]
        if finite_vals.size == 0:
            raise StepError(
                "dotplot: no finite values in the value matrix"
            )
        vmin = float(finite_vals.min())
        vmax = float(finite_vals.max())
        if vmin == vmax:
            vmin, vmax = vmin - 0.5, vmax + 0.5

        cmap_obj = plt.get_cmap(cmap)

        for gi in range(n_groups):
            for fi in range(n_features):
                v = value_matrix[gi, fi]
                p = prop_matrix[gi, fi]
                if not (np.isfinite(v) and np.isfinite(p)):
                    continue
                color = cmap_obj((v - vmin) / (vmax - vmin))
                size = max(1.0, dot_scale * p)
                ax.scatter(
                    fi, gi, s=size, c=[color],
                    edgecolors="black", linewidths=0.4,
                )

        ax.set_xticks(np.arange(n_features))
        ax.set_xticklabels(features, rotation=90, fontsize=8)
        ax.set_yticks(np.arange(n_groups))
        ax.set_yticklabels(group_order, fontsize=8)
        ax.set_xlim(-0.5, n_features - 0.5)
        ax.set_ylim(-0.5, n_groups - 0.5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle=":", alpha=0.3)
        ax.set_axisbelow(True)

        if title:
            ax.set_title(title)

        # Colorbar for value.
        from matplotlib.cm import ScalarMappable
        from matplotlib.colors import Normalize
        sm = ScalarMappable(
            cmap=cmap_obj, norm=Normalize(vmin=vmin, vmax=vmax)
        )
        sm.set_array([])
        fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02,
                     label=statistic)

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "dotplot",
            "filename": filename,
            "path": out_path,
            "feature_dim": feature_dim,
            "group_dim": group_dim,
            "group_label": group_label,
            "statistic": statistic,
            "proportion_mode": proportion_mode,
            "threshold": (
                threshold if proportion_mode == "threshold" else None
            ),
            "n_samples": len(common),
            "n_features": n_features,
            "n_groups": n_groups,
            "features": list(features),
            "groups": group_order,
            "value": {
                g: {
                    f: (
                        float(value_matrix[gi, fi])
                        if np.isfinite(value_matrix[gi, fi])
                        else None
                    )
                    for fi, f in enumerate(features)
                }
                for gi, g in enumerate(group_order)
            },
            "proportion": {
                g: {
                    f: (
                        float(prop_matrix[gi, fi])
                        if np.isfinite(prop_matrix[gi, fi])
                        else None
                    )
                    for fi, f in enumerate(features)
                }
                for gi, g in enumerate(group_order)
            },
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_features": n_features,
            "n_groups": n_groups,
            "path": out_path,
        }

        print(
            f"[dotplot] {n_groups} groups x {n_features} features "
            f"({statistic}, {proportion_mode}) -> {out_path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _decode(code, encoder):
    if encoder is None:
        try:
            f = float(code)
        except (TypeError, ValueError):
            return str(code)
        if not np.isfinite(f):
            return None
        return str(int(f)) if float(f).is_integer() else str(f)
    try:
        return str(encoder.inverse[int(code)])
    except (KeyError, ValueError, TypeError):
        return None