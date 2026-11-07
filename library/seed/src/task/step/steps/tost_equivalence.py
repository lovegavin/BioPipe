"""Two one-sided tests (TOST) for equivalence of two group means."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import group_values, labels_in_order, make_form, reorder, require_dims


class TostEquivalenceStep(Step):
    provider = 'operon-core'
    parameters_file = 'tost_equivalence.TostEquivalenceStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'tost_equivalence',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'TOST equivalence test',
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
                                         'info_open': False,
                                         'axis_info_open': False,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'TOST equivalence test：接收 2 个输入，输出 Form；主要参数：特征维度、样本维度、分组维度、分组字段、A 组、B 组。'}

    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        group_a = _group_key(ctx.step_params["group_a"])
        group_b = _group_key(ctx.step_params["group_b"])
        margin = float(ctx.step_params["margin"])
        alpha = float(ctx.step_params.get("alpha", 0.05))
        equal_var = bool(ctx.step_params.get("equal_var", False))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(expr, feature_dim, sample_dim, label="expression")
        require_dims(meta, group_dim, label="metadata")
        if margin <= 0:
            raise StepError("tost_equivalence: margin must be > 0")
        if not (0 < alpha < 0.5):
            raise StepError("tost_equivalence: alpha must be in (0, 0.5)")
        if group_a == group_b:
            raise StepError("tost_equivalence: group_a and group_b must differ")

        X = reorder(expr, sample_dim, feature_dim)
        features = labels_in_order(expr, feature_dim)
        samples = labels_in_order(expr, sample_dim)
        meta_samples, values = group_values(meta, sample_dim, group_label)
        by_sample = {sample: _group_key(value) for sample, value in zip(meta_samples, values)}
        group_codes = []
        for sample in samples:
            value = by_sample.get(sample)
            if value not in (group_a, group_b):
                continue
            group_codes.append(0 if value == group_a else 1)
        group_codes = np.asarray(group_codes, dtype=np.int64)
        if group_codes.size < 4:
            raise StepError("tost_equivalence: need at least two samples in each group")
        keep_samples = [i for i, sample in enumerate(samples) if by_sample.get(sample) in (group_a, group_b)]
        X = X[keep_samples]
        n_a = int((group_codes == 0).sum())
        n_b = int((group_codes == 1).sum())
        if n_a < 2 or n_b < 2:
            raise StepError("tost_equivalence: need at least two samples in each group")

        rows = []
        for j, feature in enumerate(features):
            a = X[group_codes == 0, j]
            b = X[group_codes == 1, j]
            a = a[np.isfinite(a)]
            b = b[np.isfinite(b)]
            if a.size < 2 or b.size < 2:
                rows.append([np.nan] * 14)
                continue
            mean_a = float(np.mean(a))
            mean_b = float(np.mean(b))
            diff = mean_a - mean_b
            var_a = float(np.var(a, ddof=1))
            var_b = float(np.var(b, ddof=1))
            if equal_var:
                df = a.size + b.size - 2
                pooled = ((a.size - 1) * var_a + (b.size - 1) * var_b) / df
                se = float(np.sqrt(pooled * (1.0 / a.size + 1.0 / b.size)))
            else:
                vn_a = var_a / a.size
                vn_b = var_b / b.size
                se = float(np.sqrt(vn_a + vn_b))
                if se == 0:
                    df = float(a.size + b.size - 2)
                else:
                    df = (vn_a + vn_b) ** 2 / (
                        vn_a ** 2 / (a.size - 1) + vn_b ** 2 / (b.size - 1)
                    )
            if se == 0:
                # Identical constant groups: equivalence depends only on the
                # observed difference relative to the margin.
                p_low = 0.0 if diff > -margin else 1.0
                p_high = 0.0 if diff < margin else 1.0
                t_low = t_high = float("inf") if diff != 0 else 0.0
                tcrit = 0.0
            else:
                t_low = (diff + margin) / se
                t_high = (diff - margin) / se
                p_low = float(stats.t.sf(t_low, df))
                p_high = float(stats.t.cdf(t_high, df))
                tcrit = float(stats.t.ppf(1.0 - alpha, df))
            p_value = max(p_low, p_high)
            ci_low = diff - tcrit * se
            ci_high = diff + tcrit * se
            rows.append([
                diff, se, df, t_low, p_low, t_high, p_high,
                p_value, float(p_value < alpha), ci_low, ci_high,
                float(a.size), float(b.size), float(mean_a - mean_b),
            ])
        columns = [
            "diff", "se", "df", "t_low", "p_low", "t_high", "p_high",
            "p", "equivalent", "ci_low", "ci_high", "n_a", "n_b", "mean_diff",
        ]
        out = make_form(
            np.asarray(rows, dtype=np.float64),
            [feature_dim, "statistic"],
            {feature_dim: {name: i for i, name in enumerate(features)},
             "statistic": {name: i for i, name in enumerate(columns)}},
        )
        ctx[out_name] = out
        self._export_data = {
            "group_a": group_a, "group_b": group_b, "margin": margin,
            "alpha": alpha, "equal_var": equal_var,
            "n_a": n_a, "n_b": n_b, "n_features": len(features),
        }
        print(
            f"[tost_equivalence] features={len(features)} {group_a}(n={n_a}) vs "
            f"{group_b}(n={n_b}) margin={margin:g}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _group_key(value) -> str:
    """Canonicalise numeric metadata values so 0, 0.0 and "0" match."""
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return str(number)
    except (TypeError, ValueError):
        return str(value)
