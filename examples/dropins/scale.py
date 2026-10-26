"""Copy this file and icons/ into the operator directory, then click Refresh."""
import numpy as np
from biopipe_sdk import Operator, Form, port, project_metadata

BIOPIPE_PLUGIN = {"name": "example-dropin-scale", "version": "0.1.0", "dependencies": ["numpy>=1.26"]}


class Scale(Operator):
    parameters_file = 'Scale.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'example.dropin_scale',
     'version': '0.1.0',
     'kind': 'operator',
     'title': 'Scale matrix',
     'description': '',
     'category': 'data',
     'icon': 'icons/scale.svg',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'transform', 'representation': 'scaled'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}

    def compute(self, inputs, params, context):
        form = inputs[0]
        info, axes = project_metadata(form, derived=True)
        data = form.data.astype(float, copy=True)
        missing = form.info.get("missing_code")
        if missing is not None:
            data[data == missing] = np.nan
        data *= params["factor"]
        info.update(representation="scaled", missing_code=float("nan"))
        return Form(data=data, dims=list(form.dims),
                    labels={d: dict(v) for d, v in form.labels.items()}, info=info, axis_info=axes)

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        cells = inputs[0].data.size
        return cells, cells * 8 + sum(len(v) for v in inputs[0].labels.values()) * 96
