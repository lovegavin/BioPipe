"""Variance inflation factor for each feature."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class VifStep(Step):
    provider = 'operon-core'
    parameters_file = 'vif.VifStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'vif',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Variance inflation factor',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
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
     'description': 'Variance inflation factor：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度。'}

    def run(self, ctx: Context, inputs) -> None:
        x, samples, features = matrix(inputs[0], ctx.step_params.get("sample_dim", "sample"), ctx.step_params.get("feature_dim", "feature"))
        n, p = x.shape
        if p < 1:
            raise StepError("at least one feature is required")
        out = np.ones((p, 1), dtype=np.float64)
        for j in range(p):
            if p == 1:
                continue
            design = np.column_stack([np.ones(n), np.delete(x, j, axis=1)])
            beta = np.linalg.lstsq(design, x[:, j], rcond=None)[0]
            resid = x[:, j] - design @ beta
            ss_res = float(np.sum(resid * resid))
            centered = x[:, j] - x[:, j].mean()
            ss_tot = float(np.sum(centered * centered))
            if ss_tot <= 0:
                out[j, 0] = float("inf")
                continue
            r2 = 1.0 - ss_res / ss_tot
            out[j, 0] = float("inf") if r2 >= 1.0 else 1.0 / max(1.0 - r2, 0.0)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(out, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={"feature": {name: i for i, name in enumerate(features)}, "statistic": {"vif": 0}},
            info={"missing_code": np.nan, "method": "vif"},
        )
        self._export = {"n_samples": n, "n_features": p}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
