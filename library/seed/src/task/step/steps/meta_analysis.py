# src/task/step/steps/meta_analysis.py
"""Fixed/random-effect meta-analysis of per-study effect sizes.

Inputs are two aligned matrices:

    effects : [variant, study] effect estimates (e.g. beta/logOR)
    stds    : [variant, study] standard errors

For each variant, fixed-effect inverse-variance pooling and the
DerSimonian-Laird random-effects estimator are computed. Cochran's Q
and I^2 (percentage, 0-100) are reported. A single study is allowed;
Q and I^2 are undefined and reported as NaN.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import (
    axis_labels,
    correct,
    labels_in_order,
    make_form,
    reorder,
    require_dims,
)

_COLUMNS = ["beta", "se", "z", "P_VALUE", "Q_VALUE", "Q", "I2", "n_studies"]
_CORRECTIONS = ("fdr", "bonferroni", "holm", "hommel", "fdr_by")


class MetaAnalysisStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'meta_analysis.MetaAnalysisStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'meta_analysis',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Meta-analysis',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'variant_dim', 'default': 'variant'},
                                        {'param': 'study_dim', 'default': 'study'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'variant_dim', 'default': 'variant'},
                                        {'param': 'study_dim', 'default': 'study'}],
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
     'description': 'Meta-analysis：接收 2 个输入，输出 Form；主要参数：Variant Dim、Study Dim、方法、Correction。'}

    def run(self, ctx: Context, inputs) -> None:
        effects, stds = inputs
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        study_dim = ctx.step_params.get("study_dim", "study")
        method = ctx.step_params.get("method", "random")
        correction = ctx.step_params.get("correction", "fdr")
        out_name = ctx.step_params.get("output", self.name)
        require_dims(effects, variant_dim, study_dim, label="effects")
        require_dims(stds, variant_dim, study_dim, label="stds")
        if dict(effects.labels[variant_dim]) != dict(stds.labels[variant_dim]):
            raise StepError("meta_analysis: effects and stds must have identical variant labels")
        if dict(effects.labels[study_dim]) != dict(stds.labels[study_dim]):
            raise StepError("meta_analysis: effects and stds must have identical study labels")
        beta = reorder(effects, variant_dim, study_dim)
        se = reorder(stds, variant_dim, study_dim)
        if beta.shape != se.shape:
            raise StepError("meta_analysis: effects and stds must have the same shape")
        if np.any(se[np.isfinite(se)] < 0):
            raise StepError("meta_analysis: standard errors must be non-negative")
        variants = labels_in_order(effects, variant_dim)
        n = beta.shape[0]
        rows = []
        for i in range(n):
            mask = np.isfinite(beta[i]) & np.isfinite(se[i]) & (se[i] > 0)
            b = beta[i][mask]
            s = se[i][mask]
            k = int(mask.sum())
            if k == 0:
                rows.append([np.nan] * len(_COLUMNS))
                continue
            w = 1.0 / (s ** 2)
            fixed = float(np.sum(w * b) / np.sum(w))
            se_fixed = float(np.sqrt(1.0 / np.sum(w)))
            if k >= 2:
                q = float(np.sum(w * (b - fixed) ** 2))
                df = k - 1
                denom = float(np.sum(w) - np.sum(w ** 2) / np.sum(w))
                tau2 = max(0.0, (q - df) / denom) if denom > 0 else 0.0
                i2 = 100.0 * max(0.0, (q - df) / q) if q > 0 else 0.0
            else:
                q = np.nan
                tau2 = 0.0
                i2 = np.nan
            if method == "random":
                wr = 1.0 / (s ** 2 + tau2)
                pooled = float(np.sum(wr * b) / np.sum(wr))
                pooled_se = float(np.sqrt(1.0 / np.sum(wr)))
            else:
                pooled, pooled_se = fixed, se_fixed
            z = pooled / pooled_se if pooled_se > 0 else np.nan
            p = float(2.0 * stats.norm.sf(abs(z))) if np.isfinite(z) else np.nan
            rows.append([pooled, pooled_se, z, p, np.nan, q, i2, k])
        stats_matrix = np.asarray(rows, dtype=np.float64)
        qvals = correct(stats_matrix[:, 3], correction)
        stats_matrix[:, 4] = qvals
        form = make_form(
            stats_matrix, [variant_dim, "statistic"],
            {variant_dim: axis_labels(variants, variant_dim),
             "statistic": {name: i for i, name in enumerate(_COLUMNS)}},
        )
        ctx[out_name] = form
        self._export_data = {
            "method": method, "n_variants": n,
            "results": [
                {"variant": variants[i], **{col: (None if not np.isfinite(stats_matrix[i, j]) else float(stats_matrix[i, j]))
                                            for j, col in enumerate(_COLUMNS)}}
                for i in range(n)
            ],
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {"method": method, "n_variants": n}

    def export(self, ctx: Context) -> dict:
        return self._export_data
