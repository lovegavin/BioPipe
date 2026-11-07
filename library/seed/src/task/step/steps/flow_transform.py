"""Arcsinh transform for FCS event matrices, matching flowCore."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, reorder, require_dims


class FlowTransformStep(Step):
    provider = 'operon-readers'
    parameters_file = 'flow_transform.FlowTransformStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'flow_transform',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Flow cytometry arcsinh transform',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'event_dim', 'default': 'event'},
                                        {'param': 'channel_dim', 'default': 'channel'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'transform', 'representation': 'flow_arcsinh'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Flow cytometry arcsinh transform：接收 1 个输入，输出 Form；主要参数：Event Dim、Channel '
                    'Dim、Channels、A、B、C。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        event_dim = ctx.step_params.get("event_dim", "event")
        channel_dim = ctx.step_params.get("channel_dim", "channel")
        require_dims(form, event_dim, channel_dim, label=self.name)
        data = np.asarray(reorder(form, event_dim, channel_dim), dtype=np.float64)
        channels = labels_in_order(form, channel_dim)
        chosen = ctx.step_params.get("channels")
        if chosen is None:
            indexes = list(range(len(channels)))
        else:
            chosen = list(chosen)
            missing = [name for name in chosen if name not in channels]
            if missing:
                raise StepError(f"{self.name}: channels not found: {missing}")
            indexes = [channels.index(name) for name in chosen]
        a = float(ctx.step_params.get("a", 1.0))
        b = float(ctx.step_params.get("b", 1.0))
        c = float(ctx.step_params.get("c", 0.0))
        transformed = data.copy()
        transformed[:, indexes] = np.arcsinh(a + b * transformed[:, indexes]) + c
        labels = {key: dict(value) for key, value in form.labels.items()}
        info = dict(form.info)
        info["representation"] = "flow_arcsinh"
        info["transform"] = {"method": "arcsinh", "a": a, "b": b, "c": c}
        out = Form(
            data=transformed.astype(np.float32),
            dims=list(form.dims),
            labels=labels,
            info=info,
            axis_info={key: dict(value) for key, value in form.axis_info.items()},
        )
        out.validate()
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "method": "arcsinh",
            "a": a,
            "b": b,
            "c": c,
            "channels": [channels[i] for i in indexes],
            "n_events": int(data.shape[0]),
        }
        print(f"[{self.name}] arcsinh(a + b*x) + c on {len(indexes)} channels")

    def export(self, ctx: Context) -> dict:
        return self._export
