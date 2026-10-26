# src/task/step/steps/select.py
"""Select step: keep a subset of labels along one dimension."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.contracts import MISSING, param, port


class SelectStep(Step):
    """Keep only the listed labels along one dimension.

    Params:
        dim    : dimension to select along
        labels : list of label names to keep, in output order
        output : context key for the result
    """
    parameters_schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
     'type': 'object',
     'properties': {'dim': {'title': '选择维度', 'type': 'string', 'x-ui-default': 'feature'},
                    'labels': {'title': '保留的标签',
                               'type': 'array',
                               'x-ui-default': ['f0', 'f1'],
                               'items': {'type': 'string'}}},
     'additionalProperties': True,
     'required': ['dim', 'labels']}
    title = '选择特征'
    category = '数据整理'
    icon = 'Selection'
    description = '按标签选择样本或特征。'

    name = "select"
    inputs_arity = 1
    outputs = []
    input_contracts = [port(dims=[param("dim")], labels=[{"dim": param("dim"), "values": param("labels")}])]
    output_contract = {"mode": "select"}
    output_parameter = "output"


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params["dim"]
        labels = ctx.step_params["labels"]
        out_name = ctx.step_params.get("output", self.name)

        if dim not in form.dims:
            raise StepError(f"select: dim '{dim}' not in {form.dims}")
        if not isinstance(labels, list) or not labels:
            raise StepError("select: 'labels' must be a non-empty list")

        dim_labels = form.labels.get(dim, {})
        if not dim_labels:
            raise StepError(
                f"select: dim '{dim}' has no labels to select from"
            )

        missing = [l for l in labels if l not in dim_labels]
        if missing:
            raise StepError(
                f"select: labels not found on dim '{dim}': {missing}. "
                f"Available: {sorted(dim_labels)}"
            )

        axis = form.dims.index(dim)
        positions = [dim_labels[l] for l in labels]

        new_form = form.subset_axis(dim, positions)
        ctx[out_name] = new_form

        self._export_data = {
            "dim": dim,
            "n_before": int(form.data.shape[axis]),
            "n_after": len(labels),
            "selected_labels": list(labels),
        }

        print(
            f"[select] dim '{dim}': {len(labels)} labels kept "
            f"-> {out_name}, shape={new_form.data.shape}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data