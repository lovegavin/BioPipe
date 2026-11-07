"""Mann-Kendall monotonic trend test per feature."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class MannKendallStep(Step):
    provider = 'operon-core'
    """Per-feature Mann-Kendall S, Kendall tau, z and two-sided p."""
    parameters_file = 'mann_kendall.MannKendallStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'mann_kendall',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Mann-Kendall trend',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'time_dim', 'default': 'time'},
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
     'description': 'Per-feature Mann-Kendall S, Kendall tau, z and two-sided p.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        time_dim = ctx.step_params.get("time_dim", "time")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        if form.data.ndim != 2 or time_dim not in form.dims or feature_dim not in form.dims:
            raise StepError(f"mann_kendall: expected 2D {time_dim!r}, {feature_dim!r}; got {form.dims}")
        axis = form.dims.index(time_dim)
        values = np.moveaxis(np.asarray(form.data, dtype=np.float64), axis, 0)
        features = [k for k, _ in sorted(form.labels[feature_dim].items(), key=lambda kv: kv[1])]
        rows = []
        for j in range(values.shape[1]):
            x = values[:, j]
            x = x[np.isfinite(x)]
            n = len(x)
            if n < 4:
                rows.append([float("nan")] * 4)
                continue
            s = 0.0
            for i in range(n - 1):
                s += float(np.sum(np.sign(x[i + 1:] - x[i])))
            counts = np.unique(x, return_counts=True)[1]
            tie = float(np.sum(counts * (counts - 1) * (2 * counts + 5)))
            var = (n * (n - 1) * (2 * n + 5) - tie) / 18.0
            if var <= 0:
                z = 0.0
                p = 1.0
            else:
                z = (s - np.sign(s)) / np.sqrt(var)
                p = float(2.0 * stats.norm.sf(abs(z)))
            tau = s / (n * (n - 1) / 2.0)
            rows.append([s, tau, z, p])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"S": 0, "tau": 1, "z": 2, "P": 3},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_timepoints": int(values.shape[0])}
        print(f"[mann_kendall] {len(features)} features, n={values.shape[0]}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
