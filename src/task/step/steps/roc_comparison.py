"""Paired DeLong test for two correlated ROC curves."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._metric_common import binary_truth, label_series, score_series


class RocComparisonStep(Step):
    """Compare two AUCs measured on the same samples (DeLong)."""

    name = "roc_comparison"
    title = "Paired ROC comparison"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 3
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("label_dim", "label")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("score_dim", "score")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("score_dim", "score")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "label_dim": {"type": "string", "default": "label"},
            "score_dim": {"type": "string", "default": "score"},
            "target_label": {"type": "string"},
            "score_a": {"type": "string"},
            "score_b": {"type": "string"},
            "positive_label": {"type": "string"},
            "confidence": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 0.999,
                "default": 0.95,
            },
            "output": {"type": "string"},
        },
        "required": ["target_label", "score_a", "score_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        label_form, score_form_a, score_form_b = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        score_dim = ctx.step_params.get("score_dim", "score")
        label_samples, labels = label_series(
            label_form,
            sample_dim,
            label_dim,
            ctx.step_params["target_label"],
            "roc_comparison",
        )
        a_samples, a_values = score_series(
            score_form_a, sample_dim, score_dim, ctx.step_params["score_a"]
        )
        b_samples, b_values = score_series(
            score_form_b, sample_dim, score_dim, ctx.step_params["score_b"]
        )
        a_map = {name: value for name, value in zip(a_samples, a_values)}
        b_map = {name: value for name, value in zip(b_samples, b_values)}
        keep = [
            i
            for i, name in enumerate(label_samples)
            if name in a_map and name in b_map
        ]
        if len(keep) < 4:
            raise StepError("roc_comparison: fewer than four shared samples")

        y_labels = [labels[i] for i in keep]
        y_a = np.asarray([a_map[label_samples[i]] for i in keep], dtype=np.float64)
        y_b = np.asarray([b_map[label_samples[i]] for i in keep], dtype=np.float64)
        valid = np.isfinite(y_a) & np.isfinite(y_b)
        y_labels = [value for value, ok in zip(y_labels, valid) if ok]
        y_a = y_a[valid]
        y_b = y_b[valid]
        if len(y_a) < 4:
            raise StepError("roc_comparison: fewer than four finite pairs")

        classes, positive, y_true = binary_truth(
            label_samples, y_labels, ctx.step_params.get("positive_label")
        )
        pos_a, pos_b = y_a[y_true == 1], y_b[y_true == 1]
        neg_a, neg_b = y_a[y_true == 0], y_b[y_true == 0]
        m, n = len(pos_a), len(neg_a)
        if m < 2 or n < 2:
            raise StepError("roc_comparison: need at least two samples in each class")

        v10_a, v01_a = _placement(pos_a, neg_a)
        v10_b, v01_b = _placement(pos_b, neg_b)
        auc_a = float(v10_a.mean())
        auc_b = float(v10_b.mean())
        s10 = float(np.cov(v10_a, v10_b, ddof=1)[0, 1])
        s01 = float(np.cov(v01_a, v01_b, ddof=1)[0, 1])
        var = (
            float(np.var(v10_a, ddof=1)) / m
            + float(np.var(v01_a, ddof=1)) / n
            + float(np.var(v10_b, ddof=1)) / m
            + float(np.var(v01_b, ddof=1)) / n
            - 2.0 * s10 / m
            - 2.0 * s01 / n
        )
        se = float(np.sqrt(max(var, 0.0)))
        difference = auc_a - auc_b
        if se > 0:
            z_value = float(difference / se)
            p_value = float(2.0 * stats.norm.sf(abs(z_value)))
        else:
            z_value = 0.0
            p_value = 1.0
        confidence = float(ctx.step_params.get("confidence", 0.95))
        zcrit = float(stats.norm.ppf(0.5 + confidence / 2.0))
        ci_low = float(np.clip(difference - zcrit * se, -1.0, 1.0))
        ci_high = float(np.clip(difference + zcrit * se, -1.0, 1.0))

        values = np.asarray(
            [
                [auc_a],
                [auc_b],
                [difference],
                [se],
                [ci_low],
                [ci_high],
                [z_value],
                [p_value],
                [float(m)],
                [float(n)],
            ],
            dtype=np.float32,
        )
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=values,
            dims=["metric", "value"],
            labels={
                "metric": {
                    "AUC_a": 0,
                    "AUC_b": 1,
                    "difference": 2,
                    "SE": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                    "z": 6,
                    "P": 7,
                    "n_pos": 8,
                    "n_neg": 9,
                },
                "value": {"value": 0},
            },
            info={
                "missing_code": np.nan,
                "method": "delong_paired",
                "positive_label": positive,
                "classes": classes,
                "confidence": confidence,
            },
        )
        self._export_data = {
            "auc_a": auc_a,
            "auc_b": auc_b,
            "difference": difference,
            "se": se,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "z": z_value,
            "p": p_value,
            "n_pos": m,
            "n_neg": n,
            "positive_label": positive,
        }
        print(
            f"[roc_comparison] AUC_a={auc_a:.4f}, AUC_b={auc_b:.4f}, "
            f"z={z_value:.4f}, P={p_value:.4g}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _placement(pos: np.ndarray, neg: np.ndarray):
    """DeLong placement values, with half credit for ties."""
    v10 = np.asarray(
        [np.mean(x > neg) + 0.5 * np.mean(x == neg) for x in pos],
        dtype=np.float64,
    )
    v01 = np.asarray(
        [np.mean(pos > y) + 0.5 * np.mean(pos == y) for y in neg],
        dtype=np.float64,
    )
    return v10, v01
