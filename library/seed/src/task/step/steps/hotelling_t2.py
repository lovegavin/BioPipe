"""Two-sample Hotelling T-squared test for multivariate means."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._tests39_common import select_groups


class HotellingT2Step(Step):
    provider = 'operon-core'
    parameters_file = 'hotelling_t2.HotellingT2Step.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'hotelling_t2',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Hotelling's T-squared",
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
                                        {'param': 'group_dim', 'default': 'feature'}],
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
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Hotelling's T-squared：接收 2 个输入，输出 Form；主要参数：特征维度、样本维度、分组维度、分组字段、A 组、B 组。"}

    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        out_name = ctx.step_params.get("output", self.name)
        data, codes, _samples, group_a, group_b = select_groups(
            expr, meta, sample_dim, feature_dim, group_dim,
            ctx.step_params["group_label"], ctx.step_params["group_a"], ctx.step_params["group_b"],
            "hotelling_t2",
        )
        data = np.asarray(data, dtype=float)
        finite = np.isfinite(data).all(axis=1)
        data = data[finite]
        codes = codes[finite]
        x = data[codes == 0]
        y = data[codes == 1]
        n1, p = x.shape
        n2 = y.shape[0]
        if n1 < 2 or n2 < 2 or p < 1:
            raise StepError("hotelling_t2: need at least two samples per group and one feature")
        if n1 + n2 - p - 1 <= 0:
            raise StepError("hotelling_t2: not enough samples for the number of features")
        diff = x.mean(axis=0) - y.mean(axis=0)
        xc = x - x.mean(axis=0)
        yc = y - y.mean(axis=0)
        pooled = (xc.T @ xc + yc.T @ yc) / (n1 + n2 - 2)
        try:
            inv = np.linalg.inv(pooled)
        except np.linalg.LinAlgError as exc:
            raise StepError("hotelling_t2: pooled covariance is singular") from exc
        t2 = float((n1 * n2 / (n1 + n2)) * diff @ inv @ diff)
        f_value = float((n1 + n2 - p - 1) / (p * (n1 + n2 - 2)) * t2)
        df1 = float(p)
        df2 = float(n1 + n2 - p - 1)
        p_value = float(stats.f.sf(f_value, df1, df2))
        out = scalar_form(
            [t2, f_value, df1, df2, p_value, float(n1), float(n2), float(p)],
            ["T2", "F", "df1", "df2", "p", "n_a", "n_b", "n_features"],
            "hotelling_t2",
        )
        out.info.update({"group_a": group_a, "group_b": group_b, "test": "f"})
        ctx[out_name] = out
        self._export_data = {
            "T2": t2, "F": f_value, "df1": df1, "df2": df2, "p": p_value,
            "n_a": int(n1), "n_b": int(n2), "n_features": int(p),
            "group_a": group_a, "group_b": group_b,
        }
        print(f"[hotelling_t2] T2={t2:.6f}, F={f_value:.6f}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
