# src/task/step/steps/boxplot.py
"""Boxplot of one value column split by groups.

Inputs
------
0. Data form with a value dim (typically the observation dim) and a
   sample dim.
1. Metadata form with the same sample dim and a column that carries
   the group labels.

The sample axis is aligned by label between the two forms. For each
group, one box is drawn for the selected value column.

Domain-agnostic. Any 2D data form + any 2D metadata form works.

Params:
    dim          : dim of the data form that holds the value column
                   (default "feature")
    value_label  : column label to plot (required)
    group_dim    : sample dim shared by both forms (required)
    group_label  : column label on the metadata's other dim
                   (required)
    groups       : optional list of group names to keep, in order
    filename     : output file name (required)
    title        : optional plot title
    xlabel       : optional x label (default: group_label)
    ylabel       : optional y label (default: value_label)
    show_points  : overlay individual points (default True)
    point_size   : marker size for overlay (default 4)
    point_alpha  : marker transparency (default 0.5)
"""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._plot_helpers import save_figure, setup_style


class BoxplotStep(Step):
    """Boxplot of one value column split by groups."""
    provider = 'biopipe-plots'
    parameters_file = 'boxplot.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'boxplot',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Boxplot',
     'description': '分组分布与散点',
     'category': '可视化',
     'icon': 'ChartLine',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': 'feature'},
                                        {'param': 'group_dim', 'default': None}],
                               'labels': [{'dim': {'param': 'dim', 'default': 'feature'},
                                           'values': {'param': 'value_label', 'default': None}}],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'group_dim', 'default': None}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2,
                               'labels_any': [{'param': 'group_label', 'default': None}]}],
                   'output': {'mode': 'none'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': None,
     'preview': {'kind': 'boxplot', 'caption': '分组分布与离群值'}}



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
        show_points = bool(ctx.step_params.get("show_points", True))
        point_size = float(ctx.step_params.get("point_size", 4))
        point_alpha = float(ctx.step_params.get("point_alpha", 0.5))

        if not value_label:
            raise StepError("boxplot: 'value_label' is required")
        if not group_dim:
            raise StepError("boxplot: 'group_dim' is required")
        if not group_label:
            raise StepError("boxplot: 'group_label' is required")
        if not filename:
            raise StepError("boxplot: 'filename' is required")
        if data_form.data.ndim != 2:
            raise StepError(
                f"boxplot: data form must be 2D, "
                f"got ndim={data_form.data.ndim}"
            )
        for d, name in (
            (dim, "dim"),
            (group_dim, "group_dim"),
        ):
            if d not in data_form.dims:
                raise StepError(
                    f"boxplot: {name} '{d}' not in data form. "
                    f"Available: {data_form.dims}"
                )
        if group_dim not in meta_form.dims:
            raise StepError(
                f"boxplot: group_dim '{group_dim}' not in metadata. "
                f"Available: {meta_form.dims}"
            )
        if dim == group_dim:
            raise StepError(
                f"boxplot: dim and group_dim are both '{dim}'"
            )

        # Align samples by label.
        data_group_labels = data_form.labels[group_dim]
        meta_group_labels = meta_form.labels[group_dim]
        common = [
            s for s in data_group_labels if s in meta_group_labels
        ]
        if len(common) < 2:
            raise StepError(
                f"boxplot: only {len(common)} common samples on "
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
                f"boxplot: value_label '{value_label}' not in dim "
                f"'{dim}'. Available: "
                f"{sorted(data_form.labels[dim])}"
            )
        value_pos = data_form.labels[dim][value_label]
        values = np.take(data_sub, value_pos, axis=feat_axis).astype(float)

        # Resolve the group column on the metadata.
        other_dims = [d for d in meta_form.dims if d != group_dim]
        if len(other_dims) != 1:
            raise StepError(
                f"boxplot: metadata must be 2D with '{group_dim}' and "
                f"one other dim, got {meta_form.dims}"
            )
        other = other_dims[0]
        if group_label not in meta_form.labels.get(other, {}):
            raise StepError(
                f"boxplot: group_label '{group_label}' not in dim "
                f"'{other}'. Available: "
                f"{sorted(meta_form.labels.get(other, {}))}"
            )
        group_pos = meta_form.labels[other][group_label]
        group_axis_meta = meta_form.dims.index(other)
        group_codes = np.take(meta_sub, group_pos, axis=group_axis_meta)

        # If the group column was encoded, we need the original names.
        encoders = meta_form.info.get("encoders", {})
        encoder = None
        if other in encoders and group_label in encoders[other]:
            encoder = encoders[other][group_label]

        # Build {group_name: [values]}.
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
                    "boxplot: 'groups' must be a non-empty list"
                )
            missing = [g for g in groups_arg if g not in by_group]
            if missing:
                raise StepError(
                    f"boxplot: groups not found: {missing}. "
                    f"Available: {sorted(by_group)}"
                )
            group_order = list(groups_arg)
        else:
            group_order = sorted(by_group.keys())

        if not group_order:
            raise StepError("boxplot: no groups with finite values")

        data_per_group = [by_group[g] for g in group_order]

        fig, ax = plt.subplots(figsize=(5.0, 4.0))

        positions = np.arange(1, len(group_order) + 1)
        bp = ax.boxplot(
            data_per_group,
            positions=positions,
            widths=0.6,
            patch_artist=True,
            showfliers=False,
        )
        for box in bp["boxes"]:
            box.set(facecolor="#D6E4F0", edgecolor="#1F4E79")
        for median in bp["medians"]:
            median.set(color="#C00000", linewidth=1.4)

        if show_points:
            rng = np.random.default_rng(0)
            for pos, values_g in zip(positions, data_per_group):
                jitter = rng.uniform(-0.15, 0.15, size=len(values_g))
                ax.scatter(
                    np.full(len(values_g), pos) + jitter,
                    values_g,
                    s=point_size, alpha=point_alpha,
                    c="#333333", edgecolors="none",
                )

        # Per-group summary counts for the export.
        summary = {}
        for g, vals in zip(group_order, data_per_group):
            arr = np.asarray(vals, dtype=float)
            summary[g] = {
                "n": int(arr.size),
                "min": float(arr.min()) if arr.size else None,
                "q25": float(np.quantile(arr, 0.25)) if arr.size else None,
                "median": float(np.median(arr)) if arr.size else None,
                "q75": float(np.quantile(arr, 0.75)) if arr.size else None,
                "max": float(arr.max()) if arr.size else None,
                "mean": float(arr.mean()) if arr.size else None,
                "std": float(arr.std()) if arr.size else None,
            }

        ax.set_xticks(positions)
        ax.set_xticklabels(group_order)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "boxplot",
            "filename": filename,
            "path": out_path,
            "dim": dim,
            "value_label": value_label,
            "group_dim": group_dim,
            "group_label": group_label,
            "n_samples": len(common),
            "n_groups": len(group_order),
            "groups": group_order,
            "summary": summary,
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_groups": len(group_order),
            "groups": group_order,
            "path": out_path,
        }

        print(
            f"[boxplot] '{value_label}' by '{group_label}': "
            f"{len(group_order)} groups, {len(common)} samples "
            f"-> {out_path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _decode_code(code, encoder):
    """Map an encoded group code back to its original name.

    If no encoder is given, treats the code as a numeric identifier:
    integer-valued floats become "0", "1", ...; non-integer floats
    keep their value as a string.
    """
    if encoder is None:
        try:
            f = float(code)
        except (TypeError, ValueError):
            return str(code)
        if not np.isfinite(f):
            return None
        if float(f).is_integer():
            return str(int(f))
        return str(f)
    try:
        return str(encoder.inverse[int(code)])
    except (KeyError, ValueError, TypeError):
        return None