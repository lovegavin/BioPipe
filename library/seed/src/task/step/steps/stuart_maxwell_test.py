"""Stuart-Maxwell test for marginal homogeneity in a square table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form, table


class StuartMaxwellTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'stuart_maxwell_test.StuartMaxwellTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'stuart_maxwell_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Stuart-Maxwell marginal homogeneity test',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'row_dim', 'default': 'row'},
                                        {'param': 'column_dim', 'default': 'column'}],
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
     'description': 'Stuart-Maxwell marginal homogeneity test：接收 1 个输入，输出 Form；主要参数：Row Dim、Column '
                    'Dim。'}

    def run(self, ctx: Context, inputs) -> None:
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        out_name = ctx.step_params.get("output", self.name)
        data, _, _ = table(inputs[0], row_dim, column_dim, self.name)
        if data.ndim != 2 or data.shape[0] != data.shape[1]:
            raise StepError("stuart_maxwell_test: table must be square")
        if np.any(data < 0):
            raise StepError("stuart_maxwell_test: table entries must be nonnegative")
        row_sums = data.sum(axis=1)
        col_sums = data.sum(axis=0)
        total = float(data.sum())
        if total <= 0:
            raise StepError("stuart_maxwell_test: table is empty")
        # R drops categories whose diagonal equals both margins; do the same
        # so Degenerate marginals do not make the covariance singular.
        equal = (np.diag(data) == row_sums) & (np.diag(data) == col_sums)
        if np.any(equal):
            data = data[~equal][:, ~equal]
            if data.shape[0] < 2:
                raise StepError("stuart_maxwell_test: too many equal marginals")
            row_sums = data.sum(axis=1)
            col_sums = data.sum(axis=0)
        k = data.shape[0]
        smd = (row_sums - col_sums)[: k - 1]
        sms = np.empty((k - 1, k - 1), dtype=float)
        for i in range(k - 1):
            for j in range(k - 1):
                if i == j:
                    sms[i, j] = row_sums[i] + col_sums[i] - 2.0 * data[i, i]
                else:
                    sms[i, j] = -(data[i, j] + data[j, i])
        if not np.isfinite(sms).all() or abs(float(np.linalg.det(sms))) < 1e-12:
            raise StepError("stuart_maxwell_test: covariance matrix is singular")
        stat = float(smd @ np.linalg.solve(sms, smd))
        df = k - 1
        p = float(stats.chi2.sf(stat, df))
        ctx[out_name] = scalar_form(
            [stat, float(df), p, total],
            ["statistic", "df", "p", "N"],
            "stuart_maxwell_test",
        )
        self._export = {"statistic": stat, "df": df, "p": p, "N": total}
        print(f"[{self.name}] chi2={stat:.4f}, df={df}, p={p:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
