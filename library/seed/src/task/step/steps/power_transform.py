"""Yeo-Johnson or Box-Cox power transform of each feature."""
from __future__ import annotations

import numpy as np
from sklearn.preprocessing import PowerTransformer

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class PowerTransformStep(Step):
    provider = 'operon-core'
    parameters_file = 'power_transform.PowerTransformStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'power_transform',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Power transform',
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
     'dependencies': ['scikit-learn'],
     'dependency_imports': ['sklearn'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Power transform：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、方法、标准化。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        x, samples, features = matrix(form, sample_dim, feature_dim)
        method = ctx.step_params.get("method", "yeo-johnson")
        if method == "box-cox" and np.any(x <= 0):
            raise StepError("box-cox requires strictly positive values")
        transformer = PowerTransformer(method=method, standardize=bool(ctx.step_params.get("standardize", True)))
        transformed = transformer.fit_transform(x)
        axis = form.dims.index(sample_dim)
        data = np.moveaxis(transformed, 0, axis)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=list(form.dims),
            labels={name: dict(values) for name, values in form.labels.items()},
            info={"missing_code": np.nan, "transform": "power", "method": method},
        )
        self._export = {"n_samples": int(x.shape[0]), "n_features": int(x.shape[1]), "method": method}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
