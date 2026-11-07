"""Chi-square goodness-of-fit test for observed category counts."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class ChisqGofStep(Step):
    provider = 'operon-core'
    parameters_file = 'chisq_gof.ChisqGofStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'chisq_gof',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Chi-square goodness-of-fit test',
        'category': 'Statistics',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1,
                'numeric': True,
                'info': {},
                'dims': [{'param': 'sample_dim', 'default': 'sample'},
                         {'param': 'feature_dim', 'default': 'feature'}],
                'labels': [],
                'parallel': [],
                'ndim': 2,
            }],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'dependencies': ['scipy>=1.11'],
        'dependency_imports': ['scipy'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Pearson chi-square goodness-of-fit test of observed counts '
                       'against uniform or user-supplied probabilities.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        counts_label = ctx.step_params["counts_label"]
        probabilities = ctx.step_params.get("probabilities")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, "chisq_gof")
        counts = np.asarray(numeric_column(frame, counts_label, "chisq_gof"),
                            dtype=np.float64)
        counts = counts[np.isfinite(counts)]
        if counts.size < 2:
            raise StepError("chisq_gof: need at least two categories")
        if np.any(counts < 0.0):
            raise StepError("chisq_gof: counts must be non-negative")
        total = float(counts.sum())
        if total <= 0.0:
            raise StepError("chisq_gof: total count must be positive")

        if probabilities is None:
            probs = np.full(counts.size, 1.0 / counts.size)
        else:
            probs = np.asarray(probabilities, dtype=np.float64)
            if probs.size != counts.size:
                raise StepError(
                    "chisq_gof: probabilities must have one entry per category")
            if np.any(~np.isfinite(probs)) or np.any(probs <= 0.0):
                raise StepError("chisq_gof: probabilities must be positive and finite")
            probs = probs / probs.sum()

        expected = probs * total
        statistic = float(((counts - expected) ** 2 / expected).sum())
        df = int(counts.size - 1)
        p_value = float(stats.chi2.sf(statistic, df))
        out = scalar_form(
            [statistic, float(df), p_value, total],
            ["statistic", "degrees_of_freedom", "p_value", "total"],
            "chisq_gof",
        )
        out.info.update({"method": "Pearson chi-square goodness-of-fit",
                         "n_categories": int(counts.size)})
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic, "degrees_of_freedom": df,
            "p_value": p_value, "total": total,
            "expected": expected.tolist(),
        }
        print(f"[chisq_gof] chi2={statistic:.6g}, df={df}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
