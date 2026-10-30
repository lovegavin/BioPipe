"""Fluorescence compensation for FCS event matrices, matching flowCore."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, reorder, require_dims


class FlowCompensateStep(Step):
    name = "flow_compensate"
    title = "Flow cytometry compensation"
    category = "Data preparation"
    builtin_package = "biopipe-readers"
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("event_dim", "event"), param("channel_dim", "channel")]),
        port(ndim=2, dims=[param("detector_dim", "detector"), param("fluorochrome_dim", "fluorochrome")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "event_dim": {"type": "string", "default": "event"},
            "channel_dim": {"type": "string", "default": "channel"},
            "detector_dim": {"type": "string", "default": "detector"},
            "fluorochrome_dim": {"type": "string", "default": "fluorochrome"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        events, spillover = inputs
        event_dim = ctx.step_params.get("event_dim", "event")
        channel_dim = ctx.step_params.get("channel_dim", "channel")
        row_dim = ctx.step_params.get("detector_dim", "detector")
        col_dim = ctx.step_params.get("fluorochrome_dim", "fluorochrome")
        require_dims(events, event_dim, channel_dim, label="events")
        require_dims(spillover, row_dim, col_dim, label="spillover")

        data = np.asarray(reorder(events, event_dim, channel_dim), dtype=np.float64)
        channels = labels_in_order(events, channel_dim)
        matrix = np.asarray(reorder(spillover, row_dim, col_dim), dtype=np.float64)
        rows = labels_in_order(spillover, row_dim)
        cols = labels_in_order(spillover, col_dim)
        if matrix.shape[0] != matrix.shape[1]:
            raise StepError("flow_compensate: spillover matrix must be square")
        if rows != cols:
            raise StepError("flow_compensate: spillover row and column labels must match")
        if len(set(cols)) != len(cols):
            raise StepError("flow_compensate: spillover labels must be unique")
        missing = [name for name in cols if name not in channels]
        if missing:
            raise StepError(f"flow_compensate: spillover channels not in event data: {missing}")
        if not np.isfinite(matrix).all():
            raise StepError("flow_compensate: spillover matrix contains non-finite values")
        try:
            inverse = np.linalg.inv(matrix)
        except np.linalg.LinAlgError as exc:
            raise StepError("flow_compensate: spillover matrix is singular") from exc
        if not np.isfinite(inverse).all():
            raise StepError("flow_compensate: spillover matrix is singular")

        indexes = [channels.index(name) for name in cols]
        compensated = data.copy()
        compensated[:, indexes] = data[:, indexes] @ inverse
        labels = {key: dict(value) for key, value in events.labels.items()}
        info = dict(events.info)
        info["compensation"] = {"method": "matrix_inverse", "channels": list(cols)}
        out = Form(
            data=compensated.astype(np.float32),
            dims=list(events.dims),
            labels=labels,
            info=info,
            axis_info={key: dict(value) for key, value in events.axis_info.items()},
        )
        out.validate()
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "method": "matrix_inverse",
            "channels": list(cols),
            "n_events": int(data.shape[0]),
            "n_channels": len(cols),
            "condition_number": float(np.linalg.cond(matrix)),
        }
        print(f"[flow_compensate] {len(cols)} channels, {data.shape[0]} events")

    def export(self, ctx: Context) -> dict:
        return self._export
