# src/task/step/steps/select.py
"""Select step: keep a subset of labels along one dimension."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step


class SelectStep(Step):
    """Keep only the listed labels along one dimension.

    Params:
        dim    : dimension to select along
        labels : list of label names to keep, in output order
        output : context key for the result
    """
    provider = 'biopipe-core'
    parameters_file = 'select.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'select',
     'version': '1.1.0',
     'kind': 'operator',
     'title': '选择特征',
     'description': '按标签选择样本或特征。',
     'category': '数据整理',
     'icon': 'Selection',
     'dependencies': ['h5py>=3'],
     'contracts': {'version': 1,
                   'inputs': [{'kind': ['form', 'file'], 'info': {}}],
                   'output': {'mode': 'choose',
                              'param': 'source_type',
                              'default': 'form',
                              'cases': {'contact_matrix': {'mode': 'declare',
                                                           'schema': {'kind': 'form',
                                                                      'numeric': True,
                                                                      'ndim': 2,
                                                                      'dims': ['bin1', 'bin2'],
                                                                      'info': {'representation': {'type': 'string',
                                                                                                  'const': 'contact_window'}},
                                                                      'info_open': True,
                                                                      'axis_info_open': True}}},
                              'otherwise': {'mode': 'select'}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}




    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        from src.core.files import FileArtifact
        if inputs and isinstance(inputs[0], FileArtifact):
            from src.task.step.steps._contact_window import estimate_window
            return estimate_window(inputs[0], params)
        return super().estimate_memory(inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        from src.core.files import FileArtifact
        if isinstance(form, FileArtifact):
            if form.format != "cool" or ctx.step_params.get("source_type") != "contact_matrix":
                raise StepError("select: file input requires source_type=contact_matrix and a Cooler file")
            from src.task.step.steps._contact_window import select_window
            selected = select_window(form, ctx.step_params, ctx=ctx)
            ctx[ctx.step_params.get("output", self.name)] = selected
            self._export_data = {"region": selected.info["region"], "region2": selected.info["region2"],
                                 "shape": list(selected.data.shape), "balanced": selected.info["balanced"]}
            return
        if ctx.step_params.get("source_type", "form") != "form":
            raise StepError("contact_matrix selection requires a Cooler file input")
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
