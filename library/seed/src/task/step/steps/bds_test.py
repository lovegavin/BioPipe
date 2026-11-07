"""BDS test for nonlinear dependence in a univariate series."""
from __future__ import annotations

import numpy as np
from statsmodels.tsa.stattools import bds

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._timeseries63_common import numeric_series


class BdsTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'bds_test.BdsTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'bds_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'BDS nonlinearity test',
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
     'dependencies': ['statsmodels>=0.14'],
     'dependency_imports': ['statsmodels'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'BDS nonlinearity test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、数值字段、Max '
                    'Dim、epsilon、Distance。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        max_dim = int(ctx.step_params.get("max_dim", 2))
        distance = float(ctx.step_params.get("distance", 1.5))
        out_name = ctx.step_params.get("output", self.name)
        _, values = numeric_series(inputs[0], sample_dim, feature_dim, value_label, self.name)
        n = int(values.size)
        if max_dim < 2:
            raise StepError("bds_test: max_dim must be at least 2")
        if n < max_dim + 2:
            raise StepError("bds_test: need more observations than max_dim + 1")
        if float(np.var(values)) <= 0:
            raise StepError("bds_test: series has no variation")
        epsilon = ctx.step_params.get("epsilon")
        if epsilon is None:
            epsilon = 0.5 * float(values.std(ddof=0))
        epsilon = float(epsilon)
        if not np.isfinite(epsilon) or epsilon <= 0:
            raise StepError("bds_test: epsilon must be positive and finite")
        try:
            statistic, pvalue = bds(values, max_dim=max_dim, epsilon=epsilon, distance=distance)
        except Exception as exc:  # pragma: no cover - statsmodels version guard
            raise StepError(f"bds_test: {exc}") from exc
        statistics = np.atleast_1d(np.asarray(statistic, dtype=np.float64))
        pvalues = np.atleast_1d(np.asarray(pvalue, dtype=np.float64))
        expected = max_dim - 1
        if statistics.size != expected or pvalues.size != expected:
            raise StepError("bds_test: unexpected statsmodels output shape")
        rows = [[float(statistics[i]), float(pvalues[i])] for i in range(expected)]
        labels = {str(dimension): dimension - 2 for dimension in range(2, max_dim + 1)}
        form = Form(
            data=np.asarray(rows, dtype=np.float64),
            dims=["dimension", "statistic"],
            labels={"dimension": labels, "statistic": {"statistic": 0, "p": 1}},
            info={
                "missing_code": np.nan,
                "method": "statsmodels_bds",
                "n": n,
                "max_dim": max_dim,
                "epsilon": epsilon,
                "distance": distance,
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "n": n,
            "max_dim": max_dim,
            "epsilon": epsilon,
            "distance": distance,
            "statistics": [
                {"dimension": dimension, "statistic": float(statistics[dimension - 2]), "p": float(pvalues[dimension - 2])}
                for dimension in range(2, max_dim + 1)
            ],
        }
        print(f"[{self.name}] n={n}, max_dim={max_dim}, epsilon={epsilon:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
