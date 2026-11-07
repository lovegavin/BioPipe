"""Raw periodogram of a univariate series."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class PeriodogramStep(Step):
    provider = 'operon-core'
    parameters_file = 'periodogram.PeriodogramStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'periodogram',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Periodogram',
        'category': 'Statistics',
        'contracts': {
            'version': 1,
            'inputs': [{'version': 1, 'numeric': True, 'info': {},
                        'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                 {'param': 'feature_dim', 'default': 'feature'}],
                        'labels': [], 'parallel': [], 'ndim': 2}],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'dependencies': ['numpy>=1.24'],
        'dependency_imports': ['numpy'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Raw periodogram (no taper, no smoothing) of one numeric '
                       'series; matches stats::spec.pgram with taper = 0 and no kernel.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        detrend = bool(ctx.step_params.get("detrend", False))
        demean = bool(ctx.step_params.get("demean", True))
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "periodogram")
        values = numeric_column(frame, value_label, "periodogram")
        if not np.isfinite(values).all():
            raise StepError("periodogram: series must be finite")
        n = values.size
        if n < 4:
            raise StepError("periodogram: need at least four observations")
        x = values.astype(np.float64).copy()
        if detrend:
            t = np.arange(1, n + 1, dtype=np.float64) - (n + 1) / 2.0
            sumt2 = n * (n * n - 1.0) / 12.0
            x = x - x.mean() - np.sum(x * t) * t / sumt2
        elif demean:
            x = x - x.mean()
        nspec = n // 2
        freq = np.arange(1, nspec + 1, dtype=np.float64) / n
        fft = np.fft.fft(x)
        spec = np.abs(fft[1:nspec + 1]) ** 2 / n
        data = np.column_stack([freq, spec])
        frequencies = {f"{value:.12g}": i for i, value in enumerate(freq)}
        ctx[out_name] = make_form(
            data,
            ["frequency", "statistic"],
            {"frequency": frequencies,
             "statistic": {"frequency": 0, "spec": 1}},
            {"method": "periodogram", "detrend": detrend, "demean": demean,
             "n_used": n, "df": 2.0},
        )
        self._export = {"frequencies": freq.tolist(), "spec": spec.tolist(),
                        "n_used": n, "detrend": detrend, "demean": demean}
        peak = int(np.argmax(spec)) if spec.size else 0
        print(f"[periodogram] n={n} bins={nspec} peak_freq={freq[peak] if spec.size else 0:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
