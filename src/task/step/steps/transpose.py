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
from src.core.contracts import MISSING, param, port


class TransposeStep(Step):
    """Reorder the axes of a form.

    Params:
        order  : list of dimension names, the desired new axis order
        output : context key for the result
    """
    parameters_schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
     'type': 'object',
     'properties': {'order': {'title': '维度顺序',
                              'type': 'array',
                              'x-ui-default': ['feature', 'sample'],
                              'items': {'type': 'string'}}},
     'additionalProperties': True,
     'required': ['order']}
    title = '维度转置'
    category = '数据整理'
    icon = 'ArrowsDownUp'
    description = '调整命名维度的排列顺序。'

    name = "transpose"
    inputs_arity = 1
    outputs = []
    input_contracts = [port(dims=param("order", []))]
    output_contract = {"mode": "transpose"}
    output_parameter = "output"


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