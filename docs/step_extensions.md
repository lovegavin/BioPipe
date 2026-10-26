# Add a Step or Operator

An extension consists of its Python implementation and its own parameter JSON.
The definition belongs to the class; parameters are authored separately. Both are
statically discoverable, so refreshing the library does not run module imports.

Save this as `scale.py`:

```python
from biopipe_sdk import Operator, Form, project_metadata

class Scale(Operator):
    parameters_file = "scale.parameters.json"
    definition = {
        "protocol_version": 3, "id": "lab.scale", "version": "0.1.0",
        "kind": "operator", "title": "Scale matrix", "category": "data",
        "inputs_arity": 1, "output_parameter": "output",
        "contracts": {"version": 1, "inputs": [{"numeric": True, "ndim": 2}],
                      "output": {"mode": "transform", "representation": "scaled"}},
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.26"], "dependency_imports": ["numpy"]
    }

    def compute(self, inputs, params, context):
        import numpy as np
        form = inputs[0]
        info, axes = project_metadata(form, derived=True)
        data = form.data.astype(float, copy=True)
        missing = form.info.get("missing_code")
        if missing is not None:
            data[data == missing] = np.nan
        data *= params["factor"]
        info.update(representation="scaled", missing_code=float("nan"))
        return Form(data, list(form.dims), {d: dict(v) for d, v in form.labels.items()}, info, axes)
```

Save the parameters beside it as `scale.parameters.json`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "factor": {"type": "number", "default": 2.0, "title": "Scale factor"}
  }
}
```

The same JSON supplies the frontend field, backend validation and execution default.
Change `default` to change new unpinned execution defaults; `x-ui-default` changes
only the new-node UI preset. Saved graph values and frozen job defaults are retained.
Each saved route owns a separate JSON of concrete node values, and each job has
its own `parameters.json`. Never load the authoring JSON inside `compute` or `run`
to replace those supplied values. See [workflow values](workflow_parameters.md).

Place both files in the operator directory shown by **Library Management**, then
refresh. For an external package, run `biopipe plugin init my_lab`, adapt its generated
code/JSON pair, run `biopipe plugin check my_lab`, `biopipe plugin test my_lab`, and
`biopipe plugin build my_lab`. Install the wheel or put the project in the inbox.
Include `*.json` and optional icons in setuptools package data.

`Step` exposes `run(ctx, inputs)` and `export(ctx)` for reports or named outputs.
`Operator.compute(inputs, params, context)` is the convenience adapter for returning
one Form. Do not mutate input Forms: other branches may reuse them. Preserve or
project `info` and `axis_info` together with the numerical transformation.

For memory planning, implement `estimate_memory(inputs, params, profiles)` and
return temporary/output byte estimates. Claim streaming only when implementing
`run_stream` with `flat-reduction-v1`; full and stream calculations must agree.
See [resource protocols](resource_runtime.md) and the executable
[`resource_plugin`](../examples/resource_plugin) example.

Optional `definition.icon` accepts an image path relative to the implementation
module. Omit it for the category's default icon. Relative paths move with the pair;
never reference a developer's home directory or installation drive.
