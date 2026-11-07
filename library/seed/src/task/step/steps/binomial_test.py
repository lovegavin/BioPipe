"""Exact binomial test for a single proportion."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class BinomialTestStep(Step):
    provider = 'operon-core'
    """Exact binomial test of ``k`` successes out of ``n`` trials.

    The p-value is the exact binomial tail (or two-sided sum of tails) and the
    confidence interval is the Clopper-Pearson exact interval, matching
    ``scipy.stats.binomtest``.
    """
    parameters_file = 'binomial_test.BinomialTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'binomial_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Exact binomial test',
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
     'description': 'Exact binomial test of ``k`` successes out of ``n`` trials.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        success_value = float(ctx.step_params.get("success_value", 1.0))
        null_probability = float(ctx.step_params.get("null_probability", 0.5))
        alternative = ctx.step_params.get("alternative", "two-sided")
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        if not 0.0 < null_probability < 1.0:
            raise StepError("binomial_test: null_probability must be strictly between 0 and 1")
        if not 0.0 < confidence < 1.0:
            raise StepError("binomial_test: confidence must be strictly between 0 and 1")
        frame = table_frame(form, sample_dim, feature_dim, "binomial_test")
        values = np.asarray(numeric_column(frame, value_label, "binomial_test"), dtype=np.float64)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 1:
            raise StepError("binomial_test: need at least one observation")
        successes = int(np.count_nonzero(values == success_value))
        result = stats.binomtest(successes, n, null_probability, alternative=alternative)
        ci = result.proportion_ci(confidence_level=confidence, method="exact")
        p_value = float(result.pvalue)
        out = scalar_form(
            [float(successes), float(n), null_probability, p_value, float(ci.low), float(ci.high), confidence],
            ["successes", "n", "p0", "p", "ci_low", "ci_high", "confidence"],
            "binomial_test",
        )
        out.info.update({"alternative": alternative, "method": "exact binomial / Clopper-Pearson"})
        ctx[out_name] = out
        self._export_data = {
            "successes": successes, "n": n, "p0": null_probability, "p": p_value,
            "ci_low": float(ci.low), "ci_high": float(ci.high),
            "confidence": confidence, "alternative": alternative,
        }
        print(f"[binomial_test] k={successes}, n={n}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
