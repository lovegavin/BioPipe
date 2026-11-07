"""Winsorise each feature at lower and upper percentiles."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class WinsorizeStep(Step):
    provider = 'operon-core'
    parameters_file = 'winsorize.WinsorizeStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'winsorize',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Winsorise',
     'category': 'Data',
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
     'description': 'Winsorise：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、Lower、Upper。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        lower = float(ctx.step_params.get("lower", 5.0))
        upper = float(ctx.step_params.get("upper", 95.0))
        if not 0 <= lower < upper <= 100:
            raise StepError("winsorize requires 0 <= lower < upper <= 100")
        x, samples, features = matrix(form, ctx.step_params.get("sample_dim", "sample"), ctx.step_params.get("feature_dim", "feature"))
        lo = np.nanpercentile(x, lower, axis=0)
        hi = np.nanpercentile(x, upper, axis=0)
        out = np.clip(x, lo, hi)
        axis = form.dims.index(ctx.step_params.get("sample_dim", "sample"))
        data = np.moveaxis(out, 0, axis)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=list(form.dims),
            labels={name: dict(values) for name, values in form.labels.items()},
            info={"missing_code": np.nan, "transform": "winsorize", "lower": lower, "upper": upper},
        )
        self._export = {"n_samples": int(x.shape[0]), "n_features": int(x.shape[1]), "lower": lower, "upper": upper}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
