"""Rectangular gating for FCS event matrices."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._ext_common import labels_in_order, reorder, require_dims



class FlowGateStep(Step):
    provider = 'operon-readers'
    parameters_file = 'flow_gate.FlowGateStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'flow_gate',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Flow cytometry rectangular gate',
     'category': 'Quality Control',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'event_dim', 'default': 'event'},
                                        {'param': 'channel_dim', 'default': 'channel'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Flow cytometry rectangular gate：接收 1 个输入，输出 Form；主要参数：Event Dim、Channel Dim、X '
                    'Channel、Y Channel、X Min、X Max。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        event_dim = ctx.step_params.get("event_dim", "event")
        channel_dim = ctx.step_params.get("channel_dim", "channel")
        require_dims(form, event_dim, channel_dim, label=self.name)
        data = np.asarray(reorder(form, event_dim, channel_dim), dtype=np.float64)
        channels = labels_in_order(form, channel_dim)
        x_name = ctx.step_params["x_channel"]
        y_name = ctx.step_params["y_channel"]
        for name in (x_name, y_name):
            if name not in channels:
                raise StepError(f"{self.name}: channel {name!r} not found in {channels}")
        x_min = float(ctx.step_params["x_min"])
        x_max = float(ctx.step_params["x_max"])
        y_min = float(ctx.step_params["y_min"])
        y_max = float(ctx.step_params["y_max"])
        if x_min > x_max or y_min > y_max:
            raise StepError(f"{self.name}: gate bounds must be ordered")
        x = data[:, channels.index(x_name)]
        y = data[:, channels.index(y_name)]
        inside = (x >= x_min) & (x <= x_max) & (y >= y_min) & (y <= y_max)
        n_total = int(x.size)
        n_inside = int(np.count_nonzero(inside))
        proportion = n_inside / n_total if n_total else float("nan")
        rows = [
            ("n_inside", float(n_inside)),
            ("proportion", float(proportion)),
            ("n_total", float(n_total)),
            ("x_min", x_min),
            ("x_max", x_max),
            ("y_min", y_min),
            ("y_max", y_max),
        ]
        ctx[ctx.step_params.get("output", self.name)] = scalar_form(
            [value for _, value in rows], [name for name, _ in rows], "flow_gate"
        )
        self._export = {
            "n_inside": n_inside,
            "proportion": proportion,
            "n_total": n_total,
            "x_channel": x_name,
            "y_channel": y_name,
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
        }
        print(f"[{self.name}] {n_inside}/{n_total} events inside rectangle")

    def export(self, ctx: Context) -> dict:
        return self._export
