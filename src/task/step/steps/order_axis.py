# src/task/step/steps/order_axis.py
"""Reorder every position along an axis by an info field.

Unlike ``prioritize``, which keeps only the top N positions,
``order_axis`` keeps every position and only changes their order.
The set of labels is unchanged; their positions along ``dim`` are
reassigned according to the ranking.

Typical uses: sort variants by genomic position before plotting,
sort samples by a covariate, sort features by variance before a
heatmap.

Layout
------
    input   dims: [..., dim, ...]
    output  dims: same as input, ``dim`` reordered

Params:
    dim        : dimension to reorder (required)
    by         : numeric info field declared parallel to ``dim``
                 (required)
    descending : True ranks largest first; False ranks smallest
                 first (default)
    output     : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step


class OrderAxisStep(Step):
    """Reorder an axis by a numeric info field, keeping all positions."""
    provider = 'biopipe-core'
    parameters_file = 'order_axis.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'order_axis',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'order_axis',
     'description': 'Reorder an axis by a numeric info field, keeping all positions.',
     'category': 'data',
     'icon': 'SortAscending',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': None}],
                               'labels': [],
                               'parallel': [{'fields': {'param': 'by', 'default': None},
                                             'dim': {'param': 'dim', 'default': None}}]}],
                   'output': {'mode': 'unknown'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}



    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        by = ctx.step_params.get("by")
        descending = bool(ctx.step_params.get("descending", False))
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("order_axis: 'dim' is required")
        if not by:
            raise StepError("order_axis: 'by' is required")
        if dim not in form.dims:
            raise StepError(
                f"order_axis: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )

        parallel = form.axis_info.get(dim, [])
        if by not in parallel:
            raise StepError(
                f"order_axis: field '{by}' is not declared parallel "
                f"to '{dim}'. Declared: {parallel}"
            )

        raw = form.info.get(by)
        if raw is None:
            raise StepError(f"order_axis: info['{by}'] is missing")

        values = np.asarray(raw, dtype=np.float64)
        axis = form.dims.index(dim)
        size = form.data.shape[axis]
        if values.shape != (size,):
            raise StepError(
                f"order_axis: info['{by}'] has shape {values.shape}, "
                f"expected ({size},)"
            )

        finite = np.isfinite(values)
        if not finite.any():
            raise StepError(
                f"order_axis: info['{by}'] has no finite values"
            )

        missing_count = int((~finite).sum())

        sorted_vals = np.where(finite, values, np.nan)
        order = np.argsort(sorted_vals, kind="stable")
        if descending:
            order = order[::-1]
        finite_order = order[finite[order]]
        missing_order = order[~finite[order]]
        order = np.concatenate([finite_order, missing_order])

        new_form = form.subset_axis(dim, order)
        ctx[out_name] = new_form

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        self._export_data = {
            "dim": dim,
            "by": by,
            "descending": descending,
            "n_positions": int(size),
            "n_missing": missing_count,
            "order": [
                {
                    "position": i,
                    "label": pos_to_label[int(pos)],
                    "value": (
                        float(values[int(pos)])
                        if np.isfinite(values[int(pos)])
                        else None
                    ),
                }
                for i, pos in enumerate(order)
            ],
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "by": by,
            "descending": descending,
        }

        print(
            f"[order_axis] '{dim}' ordered by '{by}' "
            f"({'descending' if descending else 'ascending'}), "
            f"{size} positions"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
