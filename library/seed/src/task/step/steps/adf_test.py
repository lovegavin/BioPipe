"""Augmented Dickey-Fuller unit-root test for a univariate series."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class AdfTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'adf_test.AdfTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'adf_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Augmented Dickey-Fuller test',
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
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Augmented Dickey-Fuller test：接收 1 个输入，输出 '
                    'Form；主要参数：样本维度、特征维度、数值字段、Lags、Regression。'}

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.tsa.stattools import adfuller

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        lags = ctx.step_params.get("lags")
        regression = ctx.step_params.get("regression", "ct")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 10:
            raise StepError(f"{self.name}: need at least 10 finite values")
        if lags is not None and int(lags) >= n - 2:
            raise StepError(f"{self.name}: lags must be less than n - 2")

        maxlag = None if lags is None else int(lags)
        autolag = "AIC" if lags is None else None
        try:
            result = adfuller(
                values,
                maxlag=maxlag,
                regression=regression,
                autolag=autolag,
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: ADF computation failed: {exc}") from exc

        statistic, pvalue, usedlag, nobs, critical = result[:5]
        icbest = float(result[5]) if len(result) > 5 and result[5] is not None else np.nan
        rows = [
            ("statistic", float(statistic)),
            ("p", float(pvalue)),
            ("used_lag", float(usedlag)),
            ("nobs", float(nobs)),
            ("n", float(n)),
            ("critical_1pct", float(critical["1%"])),
            ("critical_5pct", float(critical["5%"])),
            ("critical_10pct", float(critical["10%"])),
            ("ic_best", icbest),
        ]
        names = [name for name, _ in rows]
        form = make_form(
            np.asarray([[value] for _, value in rows], dtype=np.float64),
            ["statistic", "value"],
            {"statistic": {name: i for i, name in enumerate(names)}, "value": {"value": 0}},
            info={
                "method": "ADF",
                "regression": regression,
                "autolag": autolag,
                "critical": {key: float(value) for key, value in critical.items()},
                "n": n,
            },
        )
        ctx[out_name] = form
        self._export = {
            "statistic": float(statistic),
            "p": float(pvalue),
            "used_lag": int(usedlag),
            "nobs": int(nobs),
            "n": n,
            "critical": {key: float(value) for key, value in critical.items()},
            "ic_best": icbest,
        }
        print(f"[{self.name}] statistic={float(statistic):.4f}, p={float(pvalue):.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
