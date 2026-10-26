# src/task/step/steps/transpose.py
"""Transpose step: reorder the axes of a form.

Labels are unchanged: a label names a position along a named
dimension; only the axis order changes.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.forms.metadata import project_metadata


class TransposeStep(Step):
    """Reorder the axes of a form.

    Params:
        order  : list of dimension names, the desired new axis order
        output : context key for the result
    """
    provider = 'biopipe-core'
    parameters_file = 'transpose.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'transpose',
     'version': '1.0.0',
     'kind': 'operator',
     'title': '维度转置',
     'description': '调整命名维度的排列顺序。',
     'category': '数据整理',
     'icon': 'ArrowsDownUp',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': {'param': 'order', 'default': []},
                               'labels': [],
                               'parallel': []}],
                   'output': {'mode': 'transpose'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}




    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        order = ctx.step_params["order"]
        out_name = ctx.step_params.get("output", self.name)

        if not isinstance(order, list) or not order:
            raise StepError("transpose: 'order' must be a non-empty list")
        if len(order) != len(set(order)):
            raise StepError(
                f"transpose: 'order' contains duplicates: {order}"
            )
        if set(order) != set(form.dims):
            raise StepError(
                f"transpose: 'order' {order} must be a permutation of "
                f"dims {form.dims}"
            )

        axes = [form.dims.index(name) for name in order]
        new_data = np.transpose(form.data, axes=axes).copy()

        new_labels = {k: dict(v) for k, v in form.labels.items()}

        new_info, new_axis_info = project_metadata(form)
        ctx[out_name] = Form(
            data=new_data.astype(np.float32),
            dims=list(order),
            labels=new_labels,
            info=new_info,
            axis_info=new_axis_info,
        )

        self._export_data = {
            "input_dims": list(form.dims),
            "output_dims": list(order),
            "input_shape": list(form.data.shape),
            "output_shape": list(new_data.shape),
        }

        print(
            f"[transpose] {form.dims} -> {list(order)}, "
            f"shape {form.data.shape} -> {new_data.shape}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data