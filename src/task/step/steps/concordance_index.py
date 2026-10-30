"""Harrell concordance index for survival risk scores."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import port
from src.task.context import Context
from src.task.step.base import Step


class ConcordanceIndexStep(Step):
    """Harrell C-index for a survival risk column."""

    name = "concordance_index"
    title = "Concordance index"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["lifelines>=0.30"]
    dependency_imports = ["lifelines"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2)]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "time_label": {"type": "string"},
            "event_label": {"type": "string"},
            "risk_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["time_label", "event_label", "risk_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from lifelines.utils import concordance_index

        form = inputs[0]
        if form.data.ndim != 2:
            raise StepError("concordance_index: input must be 2D")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        if sample_dim not in form.dims or feature_dim not in form.dims:
            raise StepError(f"concordance_index: expected dims {sample_dim!r}, {feature_dim!r}, got {form.dims}")
        feature_labels = form.labels[feature_dim]
        for label in ("time_label", "event_label", "risk_label"):
            if ctx.step_params[label] not in feature_labels:
                raise StepError(f"concordance_index: {ctx.step_params[label]!r} not in {sorted(feature_labels)}")
        axis = form.dims.index(feature_dim)
        raw = np.asarray(form.data, dtype=np.float64)
        if axis == 1:
            raw = raw.T
        times = raw[feature_labels[ctx.step_params["time_label"]], :]
        events = raw[feature_labels[ctx.step_params["event_label"]], :]
        risk = raw[feature_labels[ctx.step_params["risk_label"]], :]
        keep = np.isfinite(times) & np.isfinite(events) & np.isfinite(risk)
        keep &= times > 0
        keep &= np.isin(events, (0, 1))
        if keep.sum() < 4:
            raise StepError("concordance_index: fewer than four usable samples")
        c_index = float(concordance_index(times[keep], -risk[keep], events[keep]))
        values = np.asarray(
            [[c_index], [float(keep.sum())], [float(events[keep].sum())]],
            dtype=np.float32,
        )
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=values,
            dims=["metric", "value"],
            labels={"metric": {"C-index": 0, "n": 1, "events": 2}, "value": {"value": 0}},
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "c_index": c_index,
            "n_samples": int(keep.sum()),
            "n_events": int(events[keep].sum()),
        }
        print(f"[concordance_index] C={c_index:.3f}, n={int(keep.sum())}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
