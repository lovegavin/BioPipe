"""Copy this file into Studio's plugin folder, then click Refresh."""
import numpy as np
from biopipe_sdk import Operator, Form, port, project_metadata

BIOPIPE_PLUGIN = {"name": "example-dropin-scale", "version": "0.1.0", "dependencies": ["numpy>=1.26"]}


class Scale(Operator):
    name = "example.dropin_scale"
    version = "0.1.0"
    title = "Scale matrix"
    category = "data"
    icon = "SlidersHorizontal"  # Optional; omit for the default icon.
    input_contracts = [port(ndim=2)]
    output_contract = {"mode": "transform", "representation": "scaled"}
    parameters_schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"factor": {"type": "number", "default": 2.0}},
    }

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
