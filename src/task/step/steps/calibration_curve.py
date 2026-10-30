"""Binned calibration curve for binary predictions."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class CalibrationCurveStep(Step):
    """Reliability curve with uniform or quantile probability bins.

    Bins with no observations are omitted. ``observed_fraction`` is the
    fraction of positive labels in the bin and ``mean_predicted`` is the mean
    predicted probability, matching ``sklearn.calibration.calibration_curve``
    for the uniform strategy.
    """

    name = "calibration_curve"
    title = "Calibration curve"
    category = "Visualization"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24"]
    dependency_imports = ["numpy"]
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
            "true_label": {"type": "string", "title": "真实标签列"},
            "prob_label": {"type": "string", "title": "预测概率列"},
            "n_bins": {"type": "integer", "minimum": 2, "maximum": 50, "default": 10},
            "strategy": {"type": "string", "enum": ["uniform", "quantile"], "default": "uniform"},
            "output": {"type": "string"},
        },
        "required": ["true_label", "prob_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        true_label = ctx.step_params["true_label"]
        prob_label = ctx.step_params["prob_label"]
        n_bins = int(ctx.step_params.get("n_bins", 10))
        strategy = ctx.step_params.get("strategy", "uniform")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, self.name)
        truth = numeric_column(frame, true_label, self.name)
        probability = numeric_column(frame, prob_label, self.name)
        keep = np.isfinite(truth) & np.isfinite(probability)
        truth = truth[keep]
        probability = probability[keep]
        if truth.size < 2:
            raise StepError(f"{self.name}: need at least two complete observations")
        if not np.all(np.isin(truth, (0.0, 1.0))):
            raise StepError(f"{self.name}: true labels must be binary 0/1")
        if np.unique(truth).size != 2:
            raise StepError(f"{self.name}: both classes are required")
        if np.any(probability < 0.0) or np.any(probability > 1.0):
            raise StepError(f"{self.name}: predicted probabilities must be in [0, 1]")

        if strategy == "uniform":
            edges = np.linspace(0.0, 1.0, n_bins + 1)
        else:
            edges = np.quantile(probability, np.linspace(0.0, 1.0, n_bins + 1))
            edges[0] = 0.0
            edges[-1] = 1.0
        order = np.argsort(probability, kind="mergesort")
        sorted_prob = probability[order]
        sorted_truth = truth[order]
        binids = np.searchsorted(edges[1:-1], sorted_prob)
        rows = []
        labels = []
        kept_edges = []
        for bin_id in range(n_bins):
            mask = binids == bin_id
            count = int(mask.sum())
            if count == 0:
                continue
            lower = float(edges[bin_id])
            upper = float(edges[bin_id + 1])
            rows.append(
                [
                    lower,
                    upper,
                    float(np.mean(sorted_prob[mask])),
                    float(np.mean(sorted_truth[mask])),
                    float(count),
                ]
            )
            labels.append(f"{lower:.6g}-{upper:.6g}")
            kept_edges.append((lower, upper))
        if not rows:
            raise StepError(f"{self.name}: no non-empty probability bins")
        ctx[out_name] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["bin", "metric"],
            labels={
                "bin": {name: i for i, name in enumerate(labels)},
                "metric": {
                    "bin_lower": 0,
                    "bin_upper": 1,
                    "mean_predicted": 2,
                    "observed_fraction": 3,
                    "n": 4,
                },
            },
            info={
                "missing_code": np.nan,
                "method": "calibration_curve",
                "strategy": strategy,
                "requested_bins": n_bins,
                "n_bins": len(rows),
                "n_samples": int(truth.size),
                "bin_edges": kept_edges,
            },
        )
        self._export_data = {
            "strategy": strategy,
            "n_bins": len(rows),
            "n_samples": int(truth.size),
            "bins": [
                {
                    "lower": row[0],
                    "upper": row[1],
                    "mean_predicted": row[2],
                    "observed_fraction": row[3],
                    "n": int(row[4]),
                }
                for row in rows
            ],
        }
        print(f"[{self.name}] {len(rows)} bins, n={truth.size}, strategy={strategy}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
