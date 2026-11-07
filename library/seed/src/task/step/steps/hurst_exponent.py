"""Simple rescaled-range (R/S) Hurst exponent."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._entropy69_common import numeric_series
from ._stats20_common import scalar_form


class HurstExponentStep(Step):
    provider = 'operon-core'
    """Simple R/S Hurst exponent, matching R pracma::hurstexp(x)$Hs.

    ``hurstexp`` pads an odd-length series with the mean of its last two
    observations before computing the simple R/S estimate.  The operator
    follows that convention so its result is exactly comparable.
    """
    parameters_file = 'hurst_exponent.HurstExponentStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'hurst_exponent',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Hurst exponent (simple R/S)',
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
     'dependencies': ['numpy>=1.24'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Simple R/S Hurst exponent, matching R pracma::hurstexp(x)$Hs.'}


    def run(self, ctx: Context, inputs) -> None:
        values = numeric_series(
            inputs[0],
            ctx.step_params.get("sample_dim", "sample"),
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params["value_label"],
            "hurst_exponent",
        )
        original_n = int(values.size)
        padded = original_n % 2 == 1
        if padded:
            values = np.append(values, 0.5 * (values[-2] + values[-1]))
        n = int(values.size)
        sd = float(np.std(values, ddof=1))
        if not np.isfinite(sd) or sd <= 0:
            raise StepError("hurst_exponent: values have zero variance")
        centered = values - float(np.mean(values))
        cumulative = np.cumsum(centered)
        span = float(np.max(cumulative) - np.min(cumulative))
        if not np.isfinite(span) or span <= 0:
            raise StepError("hurst_exponent: rescaled range is zero")
        h = float(np.log(span / sd) / np.log(n))
        out = scalar_form(
            [h, float(original_n), float(n), float(padded)],
            ["hurst", "n_original", "n_used", "padded"],
            "hurst_exponent",
        )
        out.info.update({"method": "simple rescaled range", "padding": "mean of last two" if padded else "none"})
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export_data = {"hurst": h, "n_original": original_n, "n_used": n, "padded": padded}
        print(f"[hurst_exponent] H={h:.8f}, n={n}, padded={padded}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
