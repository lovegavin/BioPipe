"""Krippendorff's alpha for nominal or interval agreement."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class KrippendorffAlphaStep(Step):
    provider = 'operon-core'
    parameters_file = 'krippendorff_alpha.KrippendorffAlphaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'krippendorff_alpha',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Krippendorff's alpha",
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'subject_dim', 'default': 'subject'},
                                        {'param': 'rater_dim', 'default': 'rater'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': [],
     'dependency_imports': [],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Krippendorff's alpha：接收 1 个输入，输出 Form；主要参数：Subject Dim、Rater Dim、Level。"}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        subject_dim = ctx.step_params.get("subject_dim", "subject")
        rater_dim = ctx.step_params.get("rater_dim", "rater")
        if form.data.ndim != 2:
            raise StepError(f"{self.name}: input must be 2D")
        if subject_dim not in form.dims or rater_dim not in form.dims:
            raise StepError(f"{self.name}: expected dims {subject_dim!r}, {rater_dim!r}, got {form.dims}")
        matrix = np.asarray(form.data, dtype=np.float64)
        if form.dims.index(subject_dim) != 0:
            matrix = matrix.T
        if matrix.shape[0] < 2 or matrix.shape[1] < 2:
            raise StepError(f"{self.name}: need at least two subjects and two raters")
        level = ctx.step_params.get("level", "nominal")

        values = np.unique(matrix[np.isfinite(matrix)])
        if values.size < 2:
            raise StepError(f"{self.name}: need at least two distinct values")
        index = {float(value): i for i, value in enumerate(values)}
        observed = np.zeros((values.size, values.size), dtype=np.float64)
        for row in matrix:
            row_values = [float(value) for value in row if np.isfinite(value)]
            m = len(row_values)
            if m < 2:
                continue
            for i, value in enumerate(row_values):
                for j, other in enumerate(row_values):
                    if i != j:
                        observed[index[value], index[other]] += 1.0 / (m - 1)
        total = float(observed.sum())
        if total <= 0:
            raise StepError(f"{self.name}: no pairable ratings")
        expected = np.outer(observed.sum(axis=1), observed.sum(axis=1)) / (total - 1.0)
        expected[np.diag_indices_from(expected)] = (
            observed.sum(axis=1) * (observed.sum(axis=1) - 1.0) / (total - 1.0)
        )
        if level == "interval":
            delta = (values[:, None] - values[None, :]) ** 2
        else:
            delta = np.ones((values.size, values.size), dtype=np.float64)
            np.fill_diagonal(delta, 0.0)
        denominator = float(np.sum(expected * delta))
        if denominator <= 0:
            raise StepError(f"{self.name}: expected disagreement is zero")
        alpha = 1.0 - float(np.sum(observed * delta)) / denominator
        data = np.asarray([[alpha, matrix.shape[0], matrix.shape[1], values.size]], dtype=np.float64)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=data,
            dims=["metric", "statistic"],
            labels={
                "metric": {"krippendorff_alpha": 0},
                "statistic": {
                    "alpha": 0,
                    "n_subjects": 1,
                    "n_raters": 2,
                    "n_categories": 3,
                },
            },
            info={"missing_code": np.nan, "level": level},
        )
        self._export_data = {
            "alpha": alpha,
            "n_subjects": int(matrix.shape[0]),
            "n_raters": int(matrix.shape[1]),
            "n_categories": int(values.size),
            "level": level,
        }
        print(f"[krippendorff_alpha] alpha={alpha:.4g}, level={level}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
