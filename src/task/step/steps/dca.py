"""Decision curve analysis for binary prediction models."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class DcaStep(Step):
    """Net benefit of a binary prediction rule across probability thresholds.

    The net benefit follows the standard decision-curve formulation
    ``TP/n - FP/n * pt/(1-pt)``. The treat-all and treat-none reference
    strategies are reported on the same threshold grid.
    """

    name = "dca"
    title = "Decision curve analysis"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24", "pandas>=2.0"]
    dependency_imports = ["numpy", "pandas"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "outcome_label": {"type": "string", "title": "二分类结局列"},
            "probability_label": {"type": "string", "title": "预测概率列"},
            "thresholds": {
                "type": "array",
                "items": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
                "title": "阈值列表（可选）",
            },
            "threshold_start": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0.01,
            },
            "threshold_stop": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0.99,
            },
            "threshold_step": {
                "type": "number",
                "exclusiveMinimum": 0,
                "maximum": 1,
                "default": 0.01,
            },
            "output": {"type": "string"},
        },
        "required": ["outcome_label", "probability_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        outcome_label = ctx.step_params["outcome_label"]
        probability_label = ctx.step_params["probability_label"]
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, self.name)
        outcome = numeric_column(frame, outcome_label, self.name)
        probability = numeric_column(frame, probability_label, self.name)
        keep = np.isfinite(outcome) & np.isfinite(probability)
        outcome = outcome[keep]
        probability = probability[keep]
        if outcome.size < 4:
            raise StepError(f"{self.name}: need at least four complete observations")
        if not np.all(np.isin(outcome, (0.0, 1.0))):
            raise StepError(f"{self.name}: outcome labels must be binary 0/1")
        if np.unique(outcome).size != 2:
            raise StepError(f"{self.name}: both outcome classes are required")
        if np.any(probability < 0.0) or np.any(probability > 1.0):
            raise StepError(f"{self.name}: predicted probabilities must be in [0, 1]")

        explicit = ctx.step_params.get("thresholds")
        if explicit is not None:
            thresholds = np.asarray(explicit, dtype=np.float64)
        else:
            start = float(ctx.step_params.get("threshold_start", 0.01))
            stop = float(ctx.step_params.get("threshold_stop", 0.99))
            step = float(ctx.step_params.get("threshold_step", 0.01))
            if not (0.0 < start < stop < 1.0):
                raise StepError(f"{self.name}: require 0 < threshold_start < threshold_stop < 1")
            if not step > 0:
                raise StepError(f"{self.name}: threshold_step must be positive")
            thresholds = np.arange(start, stop + step / 2.0, step)
        thresholds = np.unique(np.asarray(thresholds, dtype=np.float64))
        thresholds = thresholds[(thresholds > 0.0) & (thresholds < 1.0)]
        if thresholds.size < 2:
            raise StepError(f"{self.name}: need at least two thresholds in (0, 1)")
        if thresholds.size > 1000:
            raise StepError(f"{self.name}: at most 1000 thresholds are supported")

        n = int(outcome.size)
        n_positive = int(outcome.sum())
        prevalence = n_positive / n
        rows = []
        for threshold in thresholds:
            predicted = probability >= threshold
            tp = int(np.sum(predicted & (outcome == 1.0)))
            fp = int(np.sum(predicted & (outcome == 0.0)))
            odds = threshold / (1.0 - threshold)
            net_benefit = tp / n - (fp / n) * odds
            treat_all = prevalence - (1.0 - prevalence) * odds
            rows.append(
                [float(threshold), net_benefit, treat_all, 0.0, float(tp), float(fp), float(n)]
            )

        metric_names = [
            "net_benefit",
            "treat_all",
            "treat_none",
            "true_positive",
            "false_positive",
            "n",
        ]
        threshold_labels = [f"{value:.6g}" for value in thresholds]
        if len(set(threshold_labels)) != len(threshold_labels):
            threshold_labels = [f"{i}:{value:.6g}" for i, value in enumerate(thresholds)]
        ctx[out_name] = Form(
            data=np.asarray(rows, dtype=np.float64),
            dims=["threshold", "metric"],
            labels={
                "threshold": {name: i for i, name in enumerate(threshold_labels)},
                "metric": {name: i for i, name in enumerate(metric_names)},
            },
            info={
                "missing_code": np.nan,
                "method": "dca",
                "n": n,
                "n_positive": n_positive,
                "prevalence": prevalence,
            },
        )
        self._export_data = {
            "thresholds": thresholds.tolist(),
            "net_benefit": [row[1] for row in rows],
            "treat_all": [row[2] for row in rows],
            "treat_none": [row[3] for row in rows],
            "true_positive": [int(row[4]) for row in rows],
            "false_positive": [int(row[5]) for row in rows],
            "n": n,
            "prevalence": prevalence,
        }
        print(f"[{self.name}] {len(rows)} thresholds, n={n}, prevalence={prevalence:.4g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
