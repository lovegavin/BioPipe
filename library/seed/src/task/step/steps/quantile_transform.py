"""Quantile transform each feature to a normal or uniform distribution."""
from __future__ import annotations

import numpy as np
from sklearn.preprocessing import QuantileTransformer

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class QuantileTransformStep(Step):
    provider = 'operon-core'
    parameters_file = 'quantile_transform.QuantileTransformStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'quantile_transform',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Quantile transform',
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
     'description': 'Quantile transform：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、N Quantiles、Output '
                    'Distribution、随机种子。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        x, samples, features = matrix(form, sample_dim, feature_dim)
        n_quantiles = min(int(ctx.step_params.get("n_quantiles", 1000)), x.shape[0])
        transformer = QuantileTransformer(
            n_quantiles=n_quantiles,
            output_distribution=ctx.step_params.get("output_distribution", "normal"),
            random_state=int(ctx.step_params.get("random_state", 0)),
            subsample=min(x.shape[0], 100000),
        )
        transformed = transformer.fit_transform(x)
        axis = form.dims.index(sample_dim)
        data = np.moveaxis(transformed, 0, axis)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=list(form.dims),
            labels={name: dict(values) for name, values in form.labels.items()},
            info={"missing_code": np.nan, "transform": "quantile", "output_distribution": ctx.step_params.get("output_distribution", "normal")},
        )
        self._export = {"n_samples": int(x.shape[0]), "n_features": int(x.shape[1]), "n_quantiles": n_quantiles}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
