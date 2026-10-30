"""Decision-curve analysis for a binary outcome and predicted risk."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._metric_common import binary_truth, label_series, score_series


class DecisionCurveStep(Step):
    """Net benefit across risk thresholds (decision-curve analysis)."""

    name = "decision_curve"
    title = "Decision curve analysis"
    category = "Analysis"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("feature_dim", "feature")],
        )
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
            "feature_dim": {"type": "string", "default": "feature"},
            "outcome_label": {"type": "string"},
            "risk_label": {"type": "string"},
            "positive_label": {"type": "string"},
            "thresholds": {
                "type": "array",
                "items": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
                "minItems": 2,
            },
            "output": {"type": "string"},
        },
        "required": ["outcome_label", "risk_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_labels, raw_outcome = label_series(
            form,
            sample_dim,
            feature_dim,
            ctx.step_params["outcome_label"],
            "decision_curve",
        )
        _, risks = score_series(
            form, sample_dim, feature_dim, ctx.step_params["risk_label"]
        )
        if len(raw_outcome) != len(risks):
            raise StepError("decision_curve: outcome and risk lengths differ")
        keep = [
            i
            for i, (label, risk) in enumerate(zip(raw_outcome, risks))
            if label is not None and np.isfinite(risk)
        ]
        if len(keep) < 4:
            raise StepError("decision_curve: fewer than four usable samples")
        labels = [raw_outcome[i] for i in keep]
        risk = np.asarray([risks[i] for i in keep], dtype=np.float64)
        classes, positive, y = binary_truth(
            sample_labels, labels, ctx.step_params.get("positive_label")
        )
        if (risk < 0).any() or (risk > 1).any():
            raise StepError("decision_curve: risks must be in [0, 1]")
        n = len(y)
        prevalence = float(y.mean())

        raw_thresholds = ctx.step_params.get("thresholds")
        if raw_thresholds is None:
            thresholds = np.round(np.arange(0.01, 1.0, 0.01), 2)
        else:
            thresholds = np.asarray(raw_thresholds, dtype=np.float64)
            if thresholds.ndim != 1 or len(thresholds) < 2:
                raise StepError("decision_curve: thresholds must be a list of numbers")
            if ((thresholds <= 0) | (thresholds >= 1)).any():
                raise StepError("decision_curve: thresholds must be strictly in (0, 1)")
            thresholds = np.sort(thresholds)

        rows = []
        for pt in thresholds:
            predicted = risk >= pt
            tp = int(np.sum(predicted & (y == 1)))
            fp = int(np.sum(predicted & (y == 0)))
            net_benefit = tp / n - (fp / n) * (pt / (1.0 - pt))
            treat_all = prevalence - (1.0 - prevalence) * (pt / (1.0 - pt))
            rows.append(
                [float(pt), net_benefit, treat_all, 0.0, float(tp + fp), float(tp), float(fp)]
            )
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["threshold", "statistic"],
            labels={
                "threshold": {f"t{i}": i for i in range(len(rows))},
                "statistic": {
                    "threshold": 0,
                    "net_benefit": 1,
                    "treat_all": 2,
                    "treat_none": 3,
                    "n_treat": 4,
                    "true_positive": 5,
                    "false_positive": 6,
                },
            },
            info={
                "missing_code": np.nan,
                "positive_label": positive,
                "classes": classes,
                "prevalence": prevalence,
                "n": n,
            },
        )
        self._export_data = {
            "n": n,
            "prevalence": prevalence,
            "positive_label": positive,
            "n_thresholds": len(rows),
            "max_net_benefit": float(max(row[1] for row in rows)),
        }
        print(
            f"[decision_curve] n={n}, prevalence={prevalence:.3f}, "
            f"thresholds={len(rows)}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
