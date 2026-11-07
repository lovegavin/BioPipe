"""Van der Waerden normal-scores test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._tests39_common import select_groups


class VanWaerdenStep(Step):
    provider = 'operon-core'
    """Two-sample Van der Waerden normal-scores test.

    Matches ``DescTools::VanWaerdenTest``: normal scores are
    ``qnorm(rank/(n+1))`` and the statistic is
    ``(n-1)/sum(z^2) * sum((sum_g z)^2/n_g)`` with a chi-square p-value.
    """
    parameters_file = 'van_waerden.VanWaerdenStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'van_waerden',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Van der Waerden test',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'feature_dim', 'default': 'feature'},
                                        {'param': 'sample_dim', 'default': 'sample'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'group_dim', 'default': 'label'}],
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
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Two-sample Van der Waerden normal-scores test.'}


    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        group_dim = ctx.step_params.get("group_dim", "label")
        group_label = ctx.step_params["group_label"]
        group_a = ctx.step_params["group_a"]
        group_b = ctx.step_params["group_b"]
        out_name = ctx.step_params.get("output", self.name)
        data, codes, kept, a_key, b_key = select_groups(
            expr, meta, sample_dim, feature_dim, group_dim,
            group_label, group_a, group_b, "van_waerden",
        )
        statistic = 0.0
        p_value = 0.0
        n_total = 0
        n_a = 0
        n_b = 0
        for j in range(data.shape[1]):
            values = np.asarray(data[:, j], dtype=np.float64)
            keep = np.isfinite(values)
            values = values[keep]
            local_codes = codes[keep]
            if int((local_codes == 0).sum()) < 2 or int((local_codes == 1).sum()) < 2:
                raise StepError("van_waerden: each group needs at least two finite values")
            ranks = stats.rankdata(values, method="average")
            scores = stats.norm.ppf(ranks / (len(values) + 1.0))
            denom = float(np.sum(scores * scores))
            if denom <= 0 or not np.isfinite(denom):
                raise StepError("van_waerden: normal scores have zero variance")
            numerator = 0.0
            for code in (0, 1):
                group_scores = scores[local_codes == code]
                numerator += float(np.sum(group_scores) ** 2) / group_scores.size
            statistic = float((len(values) - 1.0) * numerator / denom)
            p_value = float(stats.chi2.sf(statistic, 1))
            n_total = int(len(values))
            n_a = int((local_codes == 0).sum())
            n_b = int((local_codes == 1).sum())

        out = scalar_form(
            [statistic, 1.0, p_value, float(n_total), float(n_a), float(n_b)],
            ["statistic", "df", "p", "n", "n_a", "n_b"],
            "van_waerden",
        )
        out.info.update({"groups": [a_key, b_key], "method": "normal scores"})
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic, "df": 1, "p": p_value,
            "n": n_total, "n_a": n_a, "n_b": n_b, "groups": [a_key, b_key],
        }
        print(f"[van_waerden] chi2={statistic:.6f}, p={p_value:.6g}, n={n_total}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
