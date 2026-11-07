"""Cramer's V effect size for a contingency table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form, table


class CramerVStep(Step):
    provider = 'operon-core'
    """Cramer's V with the Pearson chi-square statistic (no continuity correction)."""
    parameters_file = 'cramer_v.CramerVStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cramer_v',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Cramer's V",
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
     'description': "Cramer's V with the Pearson chi-square statistic (no continuity correction)."}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        out_name = ctx.step_params.get("output", self.name)
        counts, rows, columns = table(form, row_dim, column_dim, "cramer_v")
        if counts.ndim != 2 or min(counts.shape) < 2:
            raise StepError("cramer_v: table must have at least two rows and two columns")
        if not np.all(np.isfinite(counts)) or np.any(counts < 0):
            raise StepError("cramer_v: counts must be finite and non-negative")
        total = float(counts.sum())
        if total <= 0:
            raise StepError("cramer_v: table total must be positive")
        row_sums = counts.sum(axis=1)
        column_sums = counts.sum(axis=0)
        if np.any(row_sums <= 0) or np.any(column_sums <= 0):
            raise StepError("cramer_v: table has an empty row or column")
        expected = np.outer(row_sums, column_sums) / total
        chisq = float(np.sum((counts - expected) ** 2 / expected))
        n_rows, n_columns = counts.shape
        df = (n_rows - 1) * (n_columns - 1)
        min_dim = min(n_rows, n_columns)
        v = float(np.sqrt(chisq / (total * (min_dim - 1))))
        v = float(np.clip(v, 0.0, 1.0))
        p_value = float(stats.chi2.sf(chisq, df))
        out = scalar_form(
            [v, chisq, float(df), p_value, total, float(n_rows), float(n_columns), float(min_dim)],
            ["V", "chisq", "df", "p", "n", "n_rows", "n_columns", "min_dim"],
            "cramer_v",
        )
        out.info.update(
            {
                "row_labels": rows,
                "column_labels": columns,
                "expected_min": float(expected.min()),
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "V": v,
            "chisq": chisq,
            "df": int(df),
            "p": p_value,
            "n": int(total),
            "n_rows": int(n_rows),
            "n_columns": int(n_columns),
            "row_labels": rows,
            "column_labels": columns,
        }
        print(f"[cramer_v] V={v:.6f}, chisq={chisq:.6f}, df={df}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
