"""Anderson-Darling normality test with estimated mean and variance."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class AndersonDarlingStep(Step):
    provider = 'operon-core'
    """Anderson-Darling composite normality test.

    Uses the mean and sample standard deviation estimated from the data, as
    in ``nortest::ad.test``. The statistic is

    ``A = -n - mean((2i-1) * (log F(z_i) + log(1-F(z_{n+1-i}))))``

    and the p-value uses the adjusted statistic with the piecewise
    approximations from that implementation.
    """
    parameters_file = 'anderson_darling.AndersonDarlingStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'anderson_darling',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Anderson-Darling normality test',
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
     'dependencies': ['scipy>=1.11'],
     'dependency_imports': ['scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Anderson-Darling composite normality test.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, "anderson_darling")
        values = np.asarray(numeric_column(frame, value_label, "anderson_darling"), dtype=np.float64)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 8:
            raise StepError("anderson_darling: sample size must be at least 8")
        values = np.sort(values)
        mean = float(np.mean(values))
        sd = float(np.std(values, ddof=1))
        if sd <= 0 or not np.isfinite(sd):
            raise StepError("anderson_darling: values have zero variance")

        z = (values - mean) / sd
        log_cdf = stats.norm.logcdf(z)
        log_sf = stats.norm.logcdf(-z)
        h = (2.0 * np.arange(1, n + 1) - 1.0) * (log_cdf + log_sf[::-1])
        a_value = float(-n - np.mean(h))
        adjusted = float((1.0 + 0.75 / n + 2.25 / n ** 2) * a_value)
        if adjusted < 0.2:
            p_value = 1.0 - np.exp(-13.436 + 101.14 * adjusted - 223.73 * adjusted ** 2)
        elif adjusted < 0.34:
            p_value = 1.0 - np.exp(-8.318 + 42.796 * adjusted - 59.938 * adjusted ** 2)
        elif adjusted < 0.6:
            p_value = np.exp(0.9177 - 4.279 * adjusted - 1.38 * adjusted ** 2)
        elif adjusted < 10.0:
            p_value = np.exp(1.2937 - 5.709 * adjusted + 0.0186 * adjusted ** 2)
        else:
            p_value = 3.7e-24
        p_value = min(max(float(p_value), 0.0), 1.0)

        out = scalar_form(
            [a_value, adjusted, p_value, float(n)],
            ["A", "A_adjusted", "p", "n"],
            "anderson_darling",
        )
        out.info.update({"method": "Anderson-Darling normality", "parameters": "estimated mean and sd"})
        ctx[out_name] = out
        self._export_data = {"A": a_value, "A_adjusted": adjusted, "p": p_value, "n": n}
        print(f"[anderson_darling] A={a_value:.8f}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
