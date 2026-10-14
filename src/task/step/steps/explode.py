# src/task/step/steps/explode.py
"""Expand a multi-valued info field into separate positions.

When an info field declared parallel to ``dim`` contains a list per
position (for example semicolon-separated GO terms), this step
creates one output position per element. Other axes are replicated.

This is the standard way to turn a one-to-many annotation into a
long table that downstream grouping operators can consume.

Layout
------
    input   dims: [..., dim, ...]
    output  dims: same, with ``dim`` expanded

Params:
    dim        : dimension whose info field is exploded (required)
    field      : info field name declared parallel to ``dim``
                 (required)
    sep        : separator inside each cell (default ";")
    keep_empty : keep positions whose field is empty (default False)
    output     : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class ExplodeStep(Step):
    """Expand a multi-valued info field into separate positions."""

    name = "explode"
    category = "data"
    icon = "ArrowsDownUp"
    inputs_arity = 1
    outputs = []
    input_contracts = [
        port(
            dims=[param("dim")],
            parallel=[{"fields": param("field"), "dim": param("dim")}],
        ),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "dim": {
                "type": "string",
                "title": "Dimension to expand",
            },
            "field": {
                "type": "string",
                "title": "Multi-valued field",
                "description": (
                    "Info field declared parallel to 'dim'. Each "
                    "cell is split by 'sep'."
                ),
            },
            "sep": {
                "type": "string",
                "title": "Separator",
                "default": ";",
                "minLength": 1,
            },
            "keep_empty": {
                "type": "boolean",
                "title": "Keep empty",
                "default": False,
            },
            "output": {
                "type": "string",
                "title": "Output key",
            },
        },
        "required": ["dim", "field"],
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        field = ctx.step_params.get("field")
        sep = ctx.step_params.get("sep", ";")
        keep_empty = bool(ctx.step_params.get("keep_empty", False))
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("explode: 'dim' is required")
        if not field:
            raise StepError("explode: 'field' is required")
        if dim not in form.dims:
            raise StepError(
                f"explode: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )

        parallel = form.axis_info.get(dim, [])
        if field not in parallel:
            raise StepError(
                f"explode: field '{field}' is not declared parallel "
                f"to '{dim}'. Declared: {parallel}"
            )

        raw = form.info.get(field)
        if raw is None:
            raise StepError(f"explode: info['{field}'] is missing")

        axis = form.dims.index(dim)
        size = form.data.shape[axis]
        if len(raw) != size:
            raise StepError(
                f"explode: info['{field}'] has length {len(raw)}, "
                f"expected {size}"
            )

        cells: list[list[str]] = []
        for value in raw:
            if value is None:
                parts = []
            elif isinstance(value, str):
                parts = [p.strip() for p in value.split(sep) if p.strip()]
            elif isinstance(value, (list, tuple, np.ndarray)):
                parts = [str(p).strip() for p in value if str(p).strip()]
            else:
                parts = [str(value)]
            cells.append(parts)

        source_indices: list[int] = []
        expanded_labels: list[str] = []
        for src_pos, parts in enumerate(cells):
            if not parts and keep_empty:
                source_indices.append(src_pos)
                expanded_labels.append(f"{src_pos}#empty")
                continue
            for part in parts:
                source_indices.append(src_pos)
                expanded_labels.append(part)

        if not source_indices:
            raise StepError(
                f"explode: field '{field}' produced zero output positions"
            )

        new_data = np.take(form.data, source_indices, axis=axis).copy()

        from src.reader.readers._labels import unique_labels
        dim_labels = unique_labels(expanded_labels, dim, "explode")

        new_info = {k: v for k, v in form.info.items()}
        new_axis_info = {k: list(v) for k, v in form.axis_info.items()}

        for other_field in form.axis_info.get(dim, []):
            if other_field == field:
                continue
            other_raw = form.info.get(other_field)
            if other_raw is None:
                continue
            if isinstance(other_raw, np.ndarray):
                new_info[other_field] = other_raw[source_indices].copy()
            else:
                new_info[other_field] = [
                    other_raw[i] for i in source_indices
                ]

        new_info.pop(field, None)
        if field in new_axis_info.get(dim, []):
            new_axis_info[dim] = [
                f for f in new_axis_info[dim] if f != field
            ]
            if not new_axis_info[dim]:
                del new_axis_info[dim]

        encoders = new_info.get("encoders", {})
        if dim in encoders and field in encoders[dim]:
            encoders[dim] = {
                k: v for k, v in encoders[dim].items() if k != field
            }
            if not encoders[dim]:
                del encoders[dim]
            if encoders:
                new_info["encoders"] = encoders
            else:
                new_info.pop("encoders", None)

        new_labels = {k: dict(v) for k, v in form.labels.items()}
        new_labels[dim] = dim_labels

        out_form = Form(
            data=new_data,
            dims=list(form.dims),
            labels=new_labels,
            info=new_info,
            axis_info=new_axis_info,
        )
        out_form.validate()
        ctx[out_name] = out_form

        self._export_data = {
            "dim": dim,
            "field": field,
            "sep": sep,
            "keep_empty": keep_empty,
            "n_before": int(size),
            "n_after": len(source_indices),
            "expansion": [
                {"source": int(src), "label": lab}
                for src, lab in zip(source_indices, expanded_labels)
            ],
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "field": field,
            "n_before": int(size),
            "n_after": len(source_indices),
        }

        print(
            f"[explode] '{field}' on '{dim}': "
            f"{size} -> {len(source_indices)} positions"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
