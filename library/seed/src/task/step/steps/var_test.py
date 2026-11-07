"""F test for equality of two variances."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class VarTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'var_test.VarTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'var_test',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Two-sample F test for variances',
        'category': 'Statistics',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'numeric': True, 'info': {},
                 'dims': [{'param': 'feature_dim', 'default': 'feature'},
                          {'param': 'sample_dim', 'default': 'sample'}],
                 'labels': [], 'parallel': [], 'ndim': 2},
                {'version': 1, 'numeric': True, 'info': {},
                 'dims': [{'param': 'sample_dim', 'default': 'sample'},
                          {'param': 'group_dim', 'default': 'feature'}],
                 'labels': [], 'parallel': [], 'ndim': 2},
            ],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'dependencies': ['numpy>=1.24', 'scipy>=1.11'],
        'dependency_imports': ['numpy', 'scipy'],
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'F test for equality of two variances with an exact '
                       'chi-square based confidence interval for the ratio.',
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        alternative = ctx.step_params.get("alternative", "two-sided")
        conf_level = float(ctx.step_params.get("conf_level", 0.95))
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim,
            ctx.step_params["group_label"],
        )
        if len(columns) != 2:
            raise StepError(f"var_test needs exactly two groups, got {len(groups)}")
        rows = []
        for i in range(len(features)):
            x = np.asarray(columns[0][:, i], dtype=np.float64)
            y = np.asarray(columns[1][:, i], dtype=np.float64)
            x = x[np.isfinite(x)]
            y = y[np.isfinite(y)]
            rows.append(self._test(x, y, alternative, conf_level))
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=[feature_dim, "statistic"],
            labels={feature_dim: {name: i for i, name in enumerate(features)},
                    "statistic": {"F": 0, "df1": 1, "df2": 2, "p_value": 3,
                                  "ci_low": 4, "ci_high": 5}},
            info={"missing_code": np.nan, "method": "var_test"},
        )
        self._export = {
            "method": "var_test",
            "groups": groups,
            "features": features,
            "conf_level": conf_level,
        }
        print(f"[var_test] {len(features)} features, groups={groups}")

    @staticmethod
    def _test(x: np.ndarray, y: np.ndarray, alternative: str, conf_level: float) -> list[float]:
        nx = x.size
        ny = y.size
        if nx < 2 or ny < 2:
            raise StepError("var_test: each group needs at least two observations")
        var_x = float(np.var(x, ddof=1))
        var_y = float(np.var(y, ddof=1))
        if not var_x > 0.0 or not var_y > 0.0:
            raise StepError("var_test: both groups must have positive variance")
        f_stat = var_x / var_y
        df1 = nx - 1
        df2 = ny - 1
        lower_tail = float(stats.f.cdf(f_stat, df1, df2))
        if alternative == "less":
            p_value = lower_tail
        elif alternative == "greater":
            p_value = 1.0 - lower_tail
        else:
            p_value = min(1.0, 2.0 * min(lower_tail, 1.0 - lower_tail))
        alpha = 1.0 - conf_level
        ci_low = f_stat / float(stats.f.ppf(1.0 - alpha / 2.0, df1, df2))
        ci_high = f_stat / float(stats.f.ppf(alpha / 2.0, df1, df2))
        return [f_stat, float(df1), float(df2), float(p_value), float(ci_low), float(ci_high)]

    def export(self, ctx: Context) -> dict:
        return self._export
