"""DeLong confidence interval for a single binary-class AUC."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._metric_common import binary_truth, label_series, score_series


class DeLongAucStep(Step):
    """AUC with the DeLong variance and normal confidence interval."""

    name = "delong_auc"
    title = "DeLong AUC"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("label_dim", "label")]),
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
            "score_label": {"type": "string"},
            "positive_label": {"type": "string"},
            "confidence": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 0.999,
                "default": 0.95,
            },
            "output": {"type": "string"},
        },
        "required": ["target_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        label_form, score_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        score_dim = ctx.step_params.get("score_dim", "score")
        label_samples, labels = label_series(
            label_form,
            sample_dim,
            label_dim,
            ctx.step_params["target_label"],
            "delong_auc",
        )
        score_name = ctx.step_params.get("score_label") or next(iter(score_form.labels[score_dim]))
        score_samples, scores = score_series(
            score_form, sample_dim, score_dim, score_name
        )
        pos = {name: i for i, name in enumerate(score_samples)}
        keep = [i for i, name in enumerate(label_samples) if name in pos]
        if len(keep) < 4:
            raise StepError("delong_auc: fewer than four shared samples")
        y_labels = [labels[i] for i in keep]
        y_scores = np.asarray(
            [scores[pos[label_samples[i]]] for i in keep], dtype=np.float64
        )
        valid = np.isfinite(y_scores)
        y_labels = [v for v, ok in zip(y_labels, valid) if ok]
        y_scores = y_scores[valid]
        if len(y_scores) < 4:
            raise StepError("delong_auc: fewer than four finite scores")
        classes, positive, y_true = binary_truth(
            label_samples, y_labels, ctx.step_params.get("positive_label")
        )
        pos_scores = y_scores[y_true == 1]
        neg_scores = y_scores[y_true == 0]
        m = len(pos_scores)
        n = len(neg_scores)
        if m < 2 or n < 2:
            raise StepError("delong_auc: need at least two samples in each class")

        # DeLong placement values: for a positive case, V10 is its
        # probability of exceeding a random negative; for a control,
        # V01 is the probability of a random positive exceeding it.
        v10 = np.asarray(
            [
                np.mean(x > neg_scores) + 0.5 * np.mean(x == neg_scores)
                for x in pos_scores
            ],
            dtype=np.float64,
        )
        v01 = np.asarray(
            [
                np.mean(pos_scores > y) + 0.5 * np.mean(pos_scores == y)
                for y in neg_scores
            ],
            dtype=np.float64,
        )
        auc = float(v10.mean())
        var = float(np.var(v10, ddof=1) / m + np.var(v01, ddof=1) / n)
        se = float(np.sqrt(max(var, 0.0)))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        zcrit = float(stats.norm.ppf(0.5 + confidence / 2.0))
        ci_low = float(np.clip(auc - zcrit * se, 0.0, 1.0))
        ci_high = float(np.clip(auc + zcrit * se, 0.0, 1.0))
        z_value = float((auc - 0.5) / se) if se > 0 else float("nan")
        p_value = (
            float(2.0 * stats.norm.sf(abs(z_value)))
            if np.isfinite(z_value)
            else float("nan")
        )

        values = np.asarray(
            [
                [auc],
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
                    "AUC": 0,
                    "SE": 1,
                    "CI_low": 2,
                    "CI_high": 3,
                    "z": 4,
                    "P": 5,
                    "n_pos": 6,
                    "n_neg": 7,
                },
                "value": {"value": 0},
            },
            info={
                "missing_code": np.nan,
                "method": "delong",
                "positive_label": positive,
                "classes": classes,
                "confidence": confidence,
            },
        )
        self._export_data = {
            "auc": auc,
            "se": se,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "p": p_value,
            "n_pos": m,
            "n_neg": n,
            "positive_label": positive,
        }
        print(f"[delong_auc] AUC={auc:.4f}, SE={se:.4f}, n={m}+{n}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
