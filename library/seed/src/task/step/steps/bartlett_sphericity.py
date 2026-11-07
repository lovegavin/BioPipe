"""Bartlett's test of sphericity for a correlation matrix."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._factorability36_common import correlation_matrix
from ._stats20_common import scalar_form


class BartlettSphericityStep(Step):
    provider = 'operon-core'
    """Test whether a correlation matrix differs from the identity."""
    parameters_file = 'bartlett_sphericity.BartlettSphericityStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'bartlett_sphericity',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Bartlett sphericity test',
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
     'description': 'Test whether a correlation matrix differs from the identity.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        out_name = ctx.step_params.get("output", self.name)
        correlation, names, n = correlation_matrix(
            form, sample_dim, feature_dim, "bartlett_sphericity"
        )
        p_variables = len(names)
        sign, log_det = np.linalg.slogdet(correlation)
        if sign <= 0 or not np.isfinite(log_det):
            raise StepError("bartlett_sphericity: correlation determinant is not positive")
        statistic = float(
            -(n - 1.0 - (2.0 * p_variables + 5.0) / 6.0) * log_det
        )
        df = p_variables * (p_variables - 1) / 2.0
        p_value = float(stats.chi2.sf(statistic, df))

        out = scalar_form(
            [statistic, float(df), p_value, float(n), float(p_variables)],
            ["chisq", "df", "p", "n", "n_variables"],
            "bartlett_sphericity",
        )
        out.info.update(
            {
                "n_subjects": int(n),
                "n_variables": p_variables,
                "variables": names,
                "log_determinant": float(log_det),
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "chisq": statistic,
            "df": int(df),
            "p": p_value,
            "n": int(n),
            "n_variables": p_variables,
            "variables": names,
            "log_determinant": float(log_det),
        }
        print(
            f"[bartlett_sphericity] chisq={statistic:.6f}, df={df:g}, "
            f"p={p_value:.6g}, n={n}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
