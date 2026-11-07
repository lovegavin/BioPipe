"""Likelihood-ratio G-test for a contingency table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form, table


class GTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'g_test.GTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'g_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'G-test of independence',
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
     'dependencies': [],
     'dependency_imports': [],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'G-test of independence：接收 1 个输入，输出 Form；主要参数：Row Dim、Column Dim。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        out_name = ctx.step_params.get("output", self.name)
        counts, rows, columns = table(form, row_dim, column_dim, "g_test")
        if counts.ndim != 2 or counts.shape[0] < 2 or counts.shape[1] < 2:
            raise StepError("g_test: table must have at least two rows and two columns")
        if (counts < 0).any():
            raise StepError("g_test: counts must be non-negative")
        total = float(counts.sum())
        if total <= 0:
            raise StepError("g_test: table is empty")
        expected = np.outer(counts.sum(axis=1), counts.sum(axis=0)) / total
        if (expected <= 0).any():
            raise StepError("g_test: table has an empty row or column")
        mask = counts > 0
        g_value = float(2.0 * np.sum(counts[mask] * np.log(counts[mask] / expected[mask])))
        df = (counts.shape[0] - 1) * (counts.shape[1] - 1)
        p_value = float(stats.chi2.sf(g_value, df))
        out = scalar_form(
            [g_value, float(df), p_value, total, float(counts.shape[0]), float(counts.shape[1])],
            ["G", "df", "p", "n", "n_rows", "n_columns"],
            "g_test",
        )
        out.info.update({"row_labels": rows, "column_labels": columns, "correction": "none"})
        ctx[out_name] = out
        self._export_data = {
            "G": g_value, "df": int(df), "p": p_value, "n": int(total),
            "n_rows": int(counts.shape[0]), "n_columns": int(counts.shape[1]),
        }
        print(f"[g_test] G={g_value:.6f}, df={df}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
