"""KPSS stationarity test for a univariate series."""
from __future__ import annotations

import warnings

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class KpssTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'kpss_test.KpssTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'kpss_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'KPSS stationarity test',
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
     'description': 'KPSS stationarity test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、数值字段、Regression、Lags。'}

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.tsa.stattools import kpss

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        regression = ctx.step_params.get("regression", "c")
        lags = ctx.step_params.get("lags")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 10:
            raise StepError(f"{self.name}: need at least 10 finite values")
        if lags is not None and int(lags) >= n:
            raise StepError(f"{self.name}: lags must be less than n")

        nlags = "auto" if lags is None else int(lags)
        try:
            from statsmodels.tools.sm_exceptions import InterpolationWarning

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", InterpolationWarning)
                statistic, pvalue, used_lags, critical = kpss(
                    values, regression=regression, nlags=nlags
                )
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: KPSS computation failed: {exc}") from exc

        rows = [
            ("statistic", float(statistic)),
            ("p", float(pvalue)),
            ("lags", float(used_lags)),
            ("n", float(n)),
        ]
        for key in ("10%", "5%", "2.5%", "1%"):
            if key in critical:
                rows.append(("critical_" + key.replace(".", "_").replace("%", "pct"), float(critical[key])))
        names = [name for name, _ in rows]
        form = make_form(
            np.asarray([[value] for _, value in rows], dtype=np.float64),
            ["statistic", "value"],
            {"statistic": {name: i for i, name in enumerate(names)}, "value": {"value": 0}},
            info={
                "method": "KPSS",
                "regression": regression,
                "critical": {key: float(value) for key, value in critical.items()},
                "n": n,
            },
        )
        ctx[out_name] = form
        self._export = {
            "statistic": float(statistic),
            "p": float(pvalue),
            "lags": int(used_lags),
            "n": n,
            "critical": {key: float(value) for key, value in critical.items()},
        }
        print(f"[{self.name}] statistic={float(statistic):.4f}, p={float(pvalue):.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
