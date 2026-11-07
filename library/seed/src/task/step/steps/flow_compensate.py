"""Fluorescence compensation for FCS event matrices, matching flowCore."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, reorder, require_dims


class FlowCompensateStep(Step):
    provider = 'operon-readers'
    parameters_file = 'flow_compensate.FlowCompensateStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'flow_compensate',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Flow cytometry compensation',
     'category': 'Quality Control',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'event_dim', 'default': 'event'},
                                        {'param': 'channel_dim', 'default': 'channel'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'detector_dim', 'default': 'detector'},
                                        {'param': 'fluorochrome_dim', 'default': 'fluorochrome'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Flow cytometry compensation：接收 2 个输入，输出 Form；主要参数：Event Dim、Channel Dim、Detector '
                    'Dim、Fluorochrome Dim。'}

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
