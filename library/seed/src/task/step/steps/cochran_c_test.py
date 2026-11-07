"""Cochran's C test for one outlying group variance."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._tests50_common import grouped_expression


class CochranCTestStep(Step):
    provider = 'operon-core'
    """Cochran's C test for homogeneity of variances with equal group sizes."""
    parameters_file = 'cochran_c_test.CochranCTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cochran_c_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Cochran's C outlying variance test",
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
                               'dims': [{'param': 'group_dim', 'default': 'sample'},
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
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Cochran's C test for homogeneity of variances with equal group sizes."}


    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)
        X, features, _, groups, labels = grouped_expression(
            data, meta, sample_dim, feature_dim, group_dim, group_label
        )
        if value_label not in features:
            raise StepError(f"{self.name}: feature {value_label!r} not found")
        column = X[:, features.index(value_label)]
        group_array = np.asarray(groups)
        variances = []
        sizes = []
        for label in labels:
            values = column[group_array == label]
            values = values[np.isfinite(values)]
            if values.size < 2:
                raise StepError(f"{self.name}: group {label!r} needs at least two finite values")
            variances.append(float(np.var(values, ddof=1)))
            sizes.append(int(values.size))
        if len(set(sizes)) != 1:
            raise StepError(f"{self.name}: Cochran's C requires equal group sizes")
        if any(value <= 0 for value in variances):
            raise StepError(f"{self.name}: every group must have positive variance")
        k = len(variances)
        n = sizes[0]
        total = float(sum(variances))
        statistic = float(max(variances) / total)
        f_value = (1.0 / statistic - 1.0) / (k - 1.0)
        df1 = (n - 1) * (k - 1)
        df2 = n - 1
        p_value = float(stats.f.cdf(f_value, df1, df2) * k)
        p_value = min(1.0, max(0.0, p_value))
        outlier = labels[int(np.argmax(variances))]
        out = scalar_form(
            [statistic, p_value, float(k), float(n), float(df1), float(df2)],
            ["C", "p", "n_groups", "n_per_group", "df1", "df2"],
            self.name,
        )
        out.info.update(
            {
                "outlier_group": outlier,
                "variances": {label: variance for label, variance in zip(labels, variances)},
                "group_sizes": {label: size for label, size in zip(labels, sizes)},
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "C": statistic,
            "p": p_value,
            "n_groups": k,
            "n_per_group": n,
            "outlier_group": outlier,
            "variances": dict(zip(labels, variances)),
        }
        print(f"[{self.name}] C={statistic:.6f}, p={p_value:.6g}, outlier={outlier}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
