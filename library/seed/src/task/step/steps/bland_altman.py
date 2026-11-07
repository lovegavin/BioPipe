"""Bland-Altman agreement summary for two measurement columns."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form


class BlandAltmanStep(Step):
    provider = 'operon-core'
    parameters_file = 'bland_altman.BlandAltmanStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'bland_altman',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Bland-Altman agreement',
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
                                         'info_open': False,
                                         'axis_info_open': False,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Bland-Altman agreement：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、Method A、Method '
                    'B、Confidence。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        a_name = ctx.step_params["method_a"]
        b_name = ctx.step_params["method_b"]
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)
        if form.data.ndim != 2:
            raise StepError("bland_altman: input must be 2D")
        for dim in (sample_dim, feature_dim):
            if dim not in form.dims:
                raise StepError(f"bland_altman: dim {dim!r} not in {form.dims}")
        if not (0 < confidence < 1):
            raise StepError("bland_altman: confidence must be in (0, 1)")
        if a_name == b_name:
            raise StepError("bland_altman: method_a and method_b must differ")
        labels = form.labels.get(feature_dim, {})
        for name in (a_name, b_name):
            if name not in labels:
                raise StepError(f"bland_altman: column {name!r} not found")
        data = np.asarray(form.data, dtype=np.float64)
        if form.dims.index(sample_dim) == 1:
            data = data.T
        a = data[:, labels[a_name]]
        b = data[:, labels[b_name]]
        keep = np.isfinite(a) & np.isfinite(b)
        a, b = a[keep], b[keep]
        n = a.size
        if n < 2:
            raise StepError("bland_altman: need at least two complete pairs")
        diff = a - b
        mean_diff = float(np.mean(diff))
        sd_diff = float(np.std(diff, ddof=1))
        se_mean = sd_diff / np.sqrt(n)
        tcrit = float(stats.t.ppf(1.0 - (1.0 - confidence) / 2.0, n - 1))
        ci_low = mean_diff - tcrit * se_mean
        ci_high = mean_diff + tcrit * se_mean
        loa_low = mean_diff - 1.96 * sd_diff
        loa_high = mean_diff + 1.96 * sd_diff
        values = [
            ("mean_a", float(np.mean(a))), ("mean_b", float(np.mean(b))),
            ("mean_diff", mean_diff), ("sd_diff", sd_diff),
            ("ci_low", ci_low), ("ci_high", ci_high),
            ("loa_low", loa_low), ("loa_high", loa_high),
            ("n", float(n)),
        ]
        out = make_form(
            [[value] for _, value in values],
            ["statistic", "value"],
            {"statistic": {name: i for i, (name, _) in enumerate(values)},
             "value": {"value": 0}},
        )
        ctx[out_name] = out
        self._export_data = {
            "mean_a": float(np.mean(a)), "mean_b": float(np.mean(b)),
            "mean_diff": mean_diff, "sd_diff": sd_diff,
            "ci_low": ci_low, "ci_high": ci_high,
            "loa_low": loa_low, "loa_high": loa_high,
            "n": int(n), "confidence": confidence,
        }
        print(
            f"[bland_altman] n={n} mean_diff={mean_diff:.4g} "
            f"LoA=[{loa_low:.4g}, {loa_high:.4g}]"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
