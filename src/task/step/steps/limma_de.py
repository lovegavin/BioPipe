# src/task/step/steps/limma_de.py
"""Two-group linear-model differential analysis with empirical Bayes.

This is a limma-style workflow: per-feature group means and residual
variances, variance shrinkage using an empirical-Bayes prior, moderated
t statistics and BH correction. It is an independent Python
implementation; it is not a byte-for-byte wrapper around R limma.

The prior variance is estimated with the standard log-variance /
trigamma moment approximation used by limma's ``fitFDist``. A balanced
two-group design with ``prior_df: 0`` reduces to the ordinary pooled
t-test, which is covered by a hand-calculated test.

Output columns: logFC, mean_a, mean_b, t, P_VALUE, Q_VALUE,
df_residual, df_prior.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import (
    axis_labels,
    correct,
    group_values,
    labels_in_order,
    make_form,
    reorder,
    require_dims,
)

_COLUMNS = ["logFC", "mean_a", "mean_b", "t", "P_VALUE", "Q_VALUE",
            "df_residual", "df_prior"]
_CORRECTIONS = ("fdr", "bonferroni", "holm", "hommel", "fdr_by")


def _trigamma_inverse(value: float) -> float:
    if not np.isfinite(value) or value <= 0:
        return 0.0
    low, high = 1e-6, 1e6
    for _ in range(80):
        mid = (low + high) / 2
        if stats.distributions.gamma._trigamma(mid) < value:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _prior(s2: np.ndarray, df: int, prior_df: int | None):
    if prior_df is not None and prior_df >= 0:
        if prior_df == 0:
            return 0.0, float(np.median(s2))
        return float(prior_df), float(np.median(s2))
    finite = s2[np.isfinite(s2) & (s2 > 0)]
    if finite.size < 3:
        return 0.0, float(np.median(finite)) if finite.size else 0.0
    z = np.log(finite)
    e = stats.distributions.gamma._digamma(df / 2) - np.log(df / 2)
    var_z = float(np.var(z, ddof=1))
    var_prior = var_z - stats.distributions.gamma._trigamma(df / 2)
    if var_prior <= 0:
        return 0.0, float(np.exp(np.mean(z) - e))
    df_prior = 2.0 * _trigamma_inverse(var_prior)
    s2_prior = float(np.exp(np.mean(z) - (stats.distributions.gamma._digamma(df_prior / 2) - np.log(df_prior / 2))))
    return df_prior, s2_prior


class LimmaDeStep(Step):
    name = "limma_de"
    title = "Moderated t differential analysis"
    category = "Analysis"
    builtin_package = "biopipe-expression"
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "protein"), param("sample_dim", "sample")]),
        {**port(ndim=2, dims=[param("sample_dim", "sample")]), "labels_any": [param("group_label")]},
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "protein"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "group_a": {"type": ["string", "number"]},
            "group_b": {"type": ["string", "number"]},
            "prior_df": {"type": "integer", "minimum": 0},
            "correction": {"type": "string", "enum": list(_CORRECTIONS), "default": "fdr"},
            "output": {"type": "string"},
        },
        "required": ["group_label", "group_a", "group_b"],
    }

    def run(self, ctx: Context, inputs) -> None:
        values, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "protein")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_label = ctx.step_params["group_label"]
        group_a = ctx.step_params["group_a"]
        group_b = ctx.step_params["group_b"]
        prior_df = ctx.step_params.get("prior_df")
        correction = ctx.step_params.get("correction", "fdr")
        out_name = ctx.step_params.get("output", self.name)
        require_dims(values, feature_dim, sample_dim, label="values")
        require_dims(meta, sample_dim, label="metadata")
        if correction not in _CORRECTIONS:
            raise StepError(f"limma_de: unknown correction {correction!r}")
        meta_samples, labels = group_values(meta, sample_dim, group_label)
        labels = np.asarray(labels)
        values_samples = labels_in_order(values, sample_dim)
        index = {sample: i for i, sample in enumerate(values_samples)}
        missing = [s for s in meta_samples if s not in index]
        if missing:
            raise StepError(f"limma_de: {len(missing)} metadata samples are absent from values")
        a = np.array([index[str(s)] for s, group in zip(meta_samples, labels) if str(group) == str(group_a)])
        b = np.array([index[str(s)] for s, group in zip(meta_samples, labels) if str(group) == str(group_b)])
        if len(a) < 2 or len(b) < 2:
            raise StepError("limma_de: each group needs at least two samples")
        data = reorder(values, feature_dim, sample_dim)
        features = labels_in_order(values, feature_dim)
        xa, xb = data[:, a], data[:, b]
        ma, mb = np.nanmean(xa, axis=1), np.nanmean(xb, axis=1)
        va, vb = np.nanvar(xa, axis=1, ddof=1), np.nanvar(xb, axis=1, ddof=1)
        df = len(a) + len(b) - 2
        s2 = ((len(a) - 1) * va + (len(b) - 1) * vb) / df
        if prior_df is None:
            df_prior, s2_prior = _prior(s2, df, None)
        else:
            df_prior, s2_prior = _prior(s2, df, int(prior_df))
        if df_prior and np.isfinite(df_prior) and df_prior > 0:
            s2_post = (df_prior * s2_prior + df * s2) / (df_prior + df)
            total_df = df + df_prior
        else:
            s2_post = s2
            total_df = df
        se = np.sqrt(s2_post * (1.0 / len(a) + 1.0 / len(b)))
        logfc = mb - ma
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(se > 0, logfc / se, np.nan)
        p = 2.0 * stats.t.sf(np.abs(t), total_df)
        q = correct(p, correction)
        data_matrix = np.column_stack([logfc, ma, mb, t, p, q,
                                       np.full(len(features), df),
                                       np.full(len(features), df_prior)]).astype(np.float32)
        form = make_form(
            data_matrix, [feature_dim, "statistic"],
            {feature_dim: axis_labels(features, feature_dim),
             "statistic": {name: i for i, name in enumerate(_COLUMNS)}},
        )
        ctx[out_name] = form
        self._export_data = {
            "feature_dim": feature_dim, "group_a": group_a, "group_b": group_b,
            "n_a": len(a), "n_b": len(b), "df_residual": df,
            "df_prior": float(df_prior), "s2_prior": float(s2_prior),
            "significant": int((q < 0.05).sum()),
            "results": [
                {"feature": features[i], "logFC": float(logfc[i]),
                 "mean_a": float(ma[i]), "mean_b": float(mb[i]),
                 "t": float(t[i]), "P_VALUE": float(p[i]), "Q_VALUE": float(q[i])}
                for i in range(len(features))
            ],
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_a": len(a), "n_b": len(b), "df_prior": float(df_prior),
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data
