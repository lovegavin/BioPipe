# src/task/step/steps/violin.py
"""Violin plot of one value column split by groups.

Two inputs share a sample dim. The first carries a per-sample value
column; the second carries a group label column. For each group the
operator draws a kernel density estimate of the values, optionally
with an inner box, quartile markers, or points.

Domain-agnostic. Any 2D data form + any 2D metadata form with a
grouping column works.

Params:
    dim             : dim of the data form that holds the value
                      column (default "feature")
    value_label     : column label to plot (required)
    group_dim       : sample dim shared by both forms (required)
    group_label     : column label on the metadata's other dim
                      (required)
    groups          : optional list of group names to keep, in order
    filename        : output file name (required)
    title           : optional plot title
    xlabel          : optional x label (default: group_label)
    ylabel          : optional y label (default: value_label)
    inner           : "box" | "quartile" | "point" | "none"
                      (default "box")
    show_points     : overlay individual points (default False)
    point_size      : marker size for overlay (default 4)
    point_alpha     : marker transparency (default 0.5)
    rotate_labels   : rotate x tick labels 45 degrees (default False)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._axis_contracts import SCHEMAS, CONTRACTS, estimate_axis
from ._microbiome import metadata
from src.task.step.steps._plot_helpers import save_figure, setup_style


_INNER_MODES = ("box", "quartile", "point", "none")


class ViolinStep(Step):
    """Draw violin plots of a value column grouped by a label."""

    name = "violin"
    inputs_arity = 2
    outputs = []
    title = 'Violin plot'
    category = 'Visualization'
    builtin_package = 'biopipe-plots'
    legacy_parameters = False
    parameters_schema = SCHEMAS['violin']
    input_contracts, output_contract = CONTRACTS['violin']
    output_parameter = None

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate_axis(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        data_form, meta_form = inputs
        dim = ctx.step_params.get("dim", "feature")
        value_label = ctx.step_params.get("value_label")
        group_dim = ctx.step_params.get("group_dim")
        group_label = ctx.step_params.get("group_label")
        groups_arg = ctx.step_params.get("groups")
        filename = ctx.step_params.get("filename")
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get("xlabel", group_label)
        ylabel = ctx.step_params.get("ylabel", value_label)
        inner = ctx.step_params.get("inner", "box")
        show_points = bool(ctx.step_params.get("show_points", False))
        point_size = float(ctx.step_params.get("point_size", 4))
        point_alpha = float(ctx.step_params.get("point_alpha", 0.5))
        rotate_labels = bool(
            ctx.step_params.get("rotate_labels", False)
        )

        if not value_label:
            raise StepError("violin: 'value_label' is required")
        if not group_dim:
            raise StepError("violin: 'group_dim' is required")
        if not group_label:
            raise StepError("violin: 'group_label' is required")
        if not filename:
            raise StepError("violin: 'filename' is required")
        if inner not in _INNER_MODES:
            raise StepError(
                f"violin: inner must be one of {list(_INNER_MODES)}, "
                f"got {inner!r}"
            )
        if data_form.data.ndim != 2:
            raise StepError(
                f"violin: data form must be 2D, "
                f"got ndim={data_form.data.ndim}"
            )
        for d, name in ((dim, "dim"), (group_dim, "group_dim")):
            if d not in data_form.dims:
                raise StepError(
                    f"violin: {name} '{d}' not in data form. "
                    f"Available: {data_form.dims}"
                )
        if dim == group_dim:
            raise StepError(
                f"violin: dim and group_dim are both '{dim}'"
            )
        if group_dim not in meta_form.dims:
            raise StepError(
                f"violin: group_dim '{group_dim}' not in metadata. "
                f"Available: {meta_form.dims}"
            )

        # Align samples by label.
        data_group_labels = data_form.labels[group_dim]
        meta_group_labels = meta_form.labels[group_dim]
        common = [
            s for s in data_group_labels if s in meta_group_labels
        ]
        if len(common) < 2:
            raise StepError(
                f"violin: only {len(common)} common samples on "
                f"'{group_dim}'."
            )
        data_idx = [data_group_labels[s] for s in common]
        meta_idx = [meta_group_labels[s] for s in common]
        data_axis = data_form.dims.index(group_dim)
        meta_axis = meta_form.dims.index(group_dim)
        data_sub = np.take(data_form.data, data_idx, axis=data_axis)
        meta_sub = np.take(meta_form.data, meta_idx, axis=meta_axis)

        # Resolve the value column.
        feat_axis = data_form.dims.index(dim)
        if value_label not in data_form.labels[dim]:
            raise StepError(
                f"violin: value_label '{value_label}' not in dim "
                f"'{dim}'. Available: "
                f"{sorted(data_form.labels[dim])}"
            )
        value_pos = data_form.labels[dim][value_label]
        values = np.take(data_sub, value_pos, axis=feat_axis).astype(float)

        # Resolve the group column.
        other_dims = [d for d in meta_form.dims if d != group_dim]
        if len(other_dims) != 1:
            raise StepError(
                f"violin: metadata must be 2D with '{group_dim}' and "
                f"one other dim, got {meta_form.dims}"
            )
        other = other_dims[0]
        if group_label not in meta_form.labels.get(other, {}):
            raise StepError(
                f"violin: group_label '{group_label}' not in dim "
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

        # Build {group: [values]}.
        by_group: dict[str, list[float]] = {}
        for i, code in enumerate(group_codes):
            v = values[i]
            if not np.isfinite(v):
                continue
            name = _decode_code(code, encoder)
            if name is None:
                continue
            by_group.setdefault(name, []).append(float(v))

        if groups_arg is not None:
            if not isinstance(groups_arg, list) or not groups_arg:
                raise StepError(
                    "violin: 'groups' must be a non-empty list"
                )
            missing = [g for g in groups_arg if g not in by_group]
            if missing:
                raise StepError(
                    f"violin: groups not found: {missing}. "
                    f"Available: {sorted(by_group)}"
                )
            group_order = list(groups_arg)
        else:
            group_order = sorted(by_group.keys())

        if not group_order:
            raise StepError("violin: no groups with finite values")

        data_per_group = [np.asarray(by_group[g], dtype=float)
                          for g in group_order]
        positions = np.arange(1, len(group_order) + 1)

        fig, ax = plt.subplots(figsize=(5.0, 4.0))
        vp = ax.violinplot(
            data_per_group, positions=positions, widths=0.7,
            showmeans=False, showmedians=False, showextrema=False,
        )
        for body in vp["bodies"]:
            body.set_facecolor("#A6C8E0")
            body.set_edgecolor("#1F4E79")
            body.set_alpha(0.8)

        if inner == "box":
            _draw_inner_box(ax, data_per_group, positions)
        elif inner == "quartile":
            _draw_inner_quartiles(ax, data_per_group, positions)
        elif inner == "point":
            _draw_inner_median_points(ax, data_per_group, positions)

        if show_points:
            rng = np.random.default_rng(0)
            for pos, vals in zip(positions, data_per_group):
                jitter = rng.uniform(-0.12, 0.12, size=vals.size)
                ax.scatter(
                    np.full(vals.size, pos) + jitter, vals,
                    s=point_size, alpha=point_alpha,
                    c="#333333", edgecolors="none", zorder=2,
                )

        # Per-group summary for the export.
        summary = {}
        for g, vals in zip(group_order, data_per_group):
            n = vals.size
            summary[g] = {
                "n": int(n),
                "min": float(vals.min()) if n else None,
                "q25": float(np.quantile(vals, 0.25)) if n else None,
                "median": float(np.median(vals)) if n else None,
                "q75": float(np.quantile(vals, 0.75)) if n else None,
                "max": float(vals.max()) if n else None,
                "mean": float(vals.mean()) if n else None,
                "std": float(vals.std()) if n else None,
            }

        ax.set_xticks(positions)
        ax.set_xticklabels(
            group_order,
            rotation=45 if rotate_labels else 0,
            ha="right" if rotate_labels else "center",
        )
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "violin",
            "filename": filename,
            "path": out_path,
            "dim": dim,
            "value_label": value_label,
            "group_dim": group_dim,
            "group_label": group_label,
            "n_samples": len(common),
            "n_groups": len(group_order),
            "inner": inner,
            "groups": group_order,
            "summary": summary,
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_groups": len(group_order),
            "groups": group_order,
            "path": out_path,
        }

        print(
            f"[violin] '{value_label}' by '{group_label}': "
            f"{len(group_order)} groups, {len(common)} samples "
            f"-> {out_path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _draw_inner_box(ax, data_per_group, positions):
    bp = ax.boxplot(
        data_per_group, positions=positions, widths=0.12,
        patch_artist=True, showfliers=False,
    )
    for box in bp["boxes"]:
        box.set(facecolor="white", edgecolor="black", linewidth=0.6)
    for median in bp["medians"]:
        median.set(color="black", linewidth=1.0)


def _draw_inner_quartiles(ax, data_per_group, positions):
    for pos, vals in zip(positions, data_per_group):
        q25, q50, q75 = np.quantile(vals, [0.25, 0.5, 0.75])
        ax.vlines(pos, q25, q75, color="black", linewidth=1.2)
        ax.scatter([pos], [q50], color="white",
                   edgecolors="black", s=15, zorder=3)


def _draw_inner_median_points(ax, data_per_group, positions):
    for pos, vals in zip(positions, data_per_group):
        ax.scatter([pos], [np.median(vals)], color="white",
                   edgecolors="black", s=15, zorder=3)


def _decode_code(code, encoder):
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