# src/task/step/steps/prioritize.py
"""Keep the top positions along an axis, ranked by an info field.

Positions are sorted by a numeric info field declared parallel to
``dim``. The top ``top_n`` are retained. Their order in the output
matches their order in the source, so downstream label alignment
stays stable.

This pairs with ``annotate``: annotate writes reference columns into
``info``; prioritize selects the positions whose annotation matters
most.

Layout
------
    input   dims: [..., dim, ...]
    output  dims: same as input, with ``dim`` shortened to ``top_n``

Ranking
-------
Missing values (NaN) are ranked last regardless of direction.
Ties keep their source order (stable sort).

Params:
    dim        : dimension to sort along (required)
    by         : info field to rank by (required)
    top_n      : number of positions to keep (required)
    ascending  : False ranks largest first (default); True ranks
                 smallest first
    output     : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class PrioritizeStep(Step):
    """Keep the top positions along a dimension, ranked by an info field."""
    title = 'prioritize'
    description = 'Keep the top positions along a dimension, ranked by an info field.'

    name = "prioritize"
    category = "data"
    icon = "Funnel"
    inputs_arity = 1
    outputs = []
    input_contracts = [
        port(
            dims=[param("dim")],
            parallel=[{"fields": param("by"), "dim": param("dim")}],
        ),
    ]
    output_contract = {"mode": "subset"}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "dim": {
                "type": "string",
                "title": "Dimension to sort",
                "description": "Axis along which positions are ranked.",
            },
            "by": {
                "type": "string",
                "title": "Ranking field",
                "description": (
                    "Numeric info field declared parallel to 'dim'. "
                    "Cannot be an encoded field."
                ),
            },
            "top_n": {
                "type": "integer",
                "title": "Top N",
                "minimum": 1,
            },
            "ascending": {
                "type": "boolean",
                "title": "Ascending",
                "default": False,
                "description": (
                    "False ranks largest first; True ranks smallest first."
                ),
            },
            "output": {
                "type": "string",
                "title": "Output key",
            },
        },
        "required": ["dim", "by", "top_n"],
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        by = ctx.step_params.get("by")
        top_n = ctx.step_params.get("top_n")
        ascending = bool(ctx.step_params.get("ascending", False))
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("prioritize: 'dim' is required")
        if not by:
            raise StepError("prioritize: 'by' is required")
        if top_n is None:
            raise StepError("prioritize: 'top_n' is required")

        if dim not in form.dims:
            raise StepError(
                f"prioritize: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )

        parallel = form.axis_info.get(dim, [])
        if by not in parallel:
            raise StepError(
                f"prioritize: field '{by}' is not declared parallel "
                f"to '{dim}'. Declared: {parallel}"
            )

        encoders_for_dim = form.info.get("encoders", {}).get(dim, {})
        if by in encoders_for_dim:
            raise StepError(
                f"prioritize: field '{by}' is encoded; rank a "
                f"non-encoded numeric field"
            )

        raw = form.info.get(by)
        if raw is None:
            raise StepError(f"prioritize: info['{by}'] is missing")

        values = np.asarray(raw, dtype=np.float64)
        axis = form.dims.index(dim)
        size = form.data.shape[axis]
        if values.shape != (size,):
            raise StepError(
                f"prioritize: info['{by}'] has shape {values.shape}, "
                f"expected ({size},)"
            )

        finite = np.isfinite(values)
        if not finite.any():
            raise StepError(
                f"prioritize: info['{by}'] has no finite values"
            )

        if top_n < 1:
            raise StepError(
                f"prioritize: top_n must be >= 1, got {top_n}"
            )
        if top_n > size:
            raise StepError(
                f"prioritize: top_n={top_n} exceeds dim size {size}"
            )

        sorted_vals = np.where(finite, values, np.nan)
        order = np.argsort(sorted_vals, kind="stable")
        if not ascending:
            order = order[::-1]
        finite_order = order[finite[order]]
        missing_order = order[~finite[order]]
        order = np.concatenate([finite_order, missing_order])

        kept = order[:top_n]
        kept_sorted = np.sort(kept)

        new_form = form.subset_axis(dim, kept_sorted)
        ctx[out_name] = new_form

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        kept_set = set(kept.tolist())
        rank_position = {
            int(pos): rank + 1 for rank, pos in enumerate(order)
        }

        self._export_data = {
            "dim": dim,
            "by": by,
            "ascending": ascending,
            "top_n": top_n,
            "n_before": int(size),
            "n_after": int(top_n),
            "kept_labels": [
                pos_to_label[int(i)] for i in kept_sorted
            ],
            "ranking": [
                {
                    "rank": rank_position[int(pos)],
                    "label": pos_to_label[int(pos)],
                    "value": (
                        float(values[int(pos)])
                        if np.isfinite(values[int(pos)])
                        else None
                    ),
                }
                for pos in order
                if int(pos) in kept_set
            ],
            "n_excluded": int(size - top_n),
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "by": by,
            "top_n": top_n,
        }

        print(
            f"[prioritize] '{dim}' ranked by '{by}' "
            f"({'ascending' if ascending else 'descending'}), "
            f"kept {top_n}/{size}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
