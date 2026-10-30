# src/task/step/steps/drop.py
"""Drop step: remove named labels from one dimension."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step


class DropStep(Step):
    """Remove a set of labels from one dimension.

    Params:
        dim    : dimension from which to drop
        labels : list of label names to remove
        output : context key for the result
    """
    provider = 'biopipe-core'
    parameters_file = 'drop.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'drop',
     'version': '1.0.0',
     'kind': 'operator',
     'title': '移除特征',
     'description': '移除指定维度上的标签。',
     'category': '数据整理',
     'icon': 'MinusSquare',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': None}],
                               'labels': [{'dim': {'param': 'dim', 'default': None},
                                           'values': {'param': 'labels', 'default': None}}],
                               'parallel': []}],
                   'output': {'mode': 'drop'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}




    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params["dim"]
        labels = ctx.step_params["labels"]
        out_name = ctx.step_params.get("output", self.name)

        if dim not in form.dims:
            raise StepError(f"drop: dim '{dim}' not in {form.dims}")

        axis = form.dims.index(dim)
        dim_labels = form.labels.get(dim, {})

        drop_positions = set()
        for lab in labels:
            if lab not in dim_labels:
                raise StepError(
                    f"drop: label '{lab}' not found on dim '{dim}'. "
                    f"Available: {sorted(dim_labels)}"
                )
            drop_positions.add(dim_labels[lab])

        size = form.data.shape[axis]
        keep = [i for i in range(size) if i not in drop_positions]

        if not keep:
            raise StepError(
                f"drop: removing {sorted(labels)} would empty dim "
                f"'{dim}'. Refuse to produce a form with zero positions."
            )

        new_form = form.subset_axis(dim, keep)
        ctx[out_name] = new_form

        self._export_data = {
            "dim": dim,
            "n_before": int(size),
            "n_after": len(keep),
            "dropped_labels": list(labels),
        }

        print(
            f"[drop] removed {len(drop_positions)} from '{dim}' "
            f"-> {out_name}, shape={new_form.data.shape}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data