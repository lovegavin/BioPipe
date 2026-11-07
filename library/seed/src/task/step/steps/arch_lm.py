"""Engle's Lagrange-multiplier test for autoregressive conditional heteroskedasticity."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class ArchLmStep(Step):
    provider = 'operon-core'
    """ARCH LM test on a residual or return series.

    The input is treated as residuals; the operator does not fit a mean model.
    """
    parameters_file = 'arch_lm.ArchLmStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'arch_lm',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'ARCH LM test',
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
     'description': 'ARCH LM test on a residual or return series.'}


    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.stats.diagnostic import het_arch

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        lags = int(ctx.step_params.get("lags", 12))
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 10:
            raise StepError(f"{self.name}: need at least 10 finite residuals")
        if lags < 1:
            raise StepError(f"{self.name}: lags must be at least 1")
        if lags >= n - 1:
            raise StepError(f"{self.name}: lags must be less than n - 1")

        try:
            statistic, p_value, f_statistic, f_p_value = het_arch(values, nlags=lags)
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: ARCH LM computation failed: {exc}") from exc

        rows = [
            ("statistic", float(statistic)),
            ("p", float(p_value)),
            ("df", float(lags)),
            ("f_statistic", float(f_statistic)),
            ("f_p", float(f_p_value)),
            ("lags", float(lags)),
            ("n", float(n)),
        ]
        names = [name for name, _ in rows]
        form = Form(
            data=np.asarray([[value] for _, value in rows], dtype=np.float64),
            dims=["statistic", "value"],
            labels={"statistic": {name: i for i, name in enumerate(names)}, "value": {"value": 0}},
            info={
                "missing_code": np.nan,
                "method": "Engle ARCH LM",
                "lags": lags,
                "n": n,
                "null": "no ARCH effects",
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "statistic": float(statistic),
            "p": float(p_value),
            "df": lags,
            "f_statistic": float(f_statistic),
            "f_p": float(f_p_value),
            "lags": lags,
            "n": n,
        }
        print(f"[{self.name}] LM={float(statistic):.6f}, p={float(p_value):.6g}, lags={lags}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
