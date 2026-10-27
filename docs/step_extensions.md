# Add a Step or Operator

> 入口：[文档首页](README.md) / [架构总览](architecture.md) / [协议总集](protocol_suite.md)。本文是实现细节；冲突时以架构/协议总集为准。

Use `Operator` for a function that consumes Forms and returns one Form or a report.
It is a small adapter over the existing `Step` API. Use `Step` directly when you
need the established `run(ctx, inputs)` / `export(ctx)` lifecycle or named outputs.
Both use identical discovery, dependency declarations and contracts.

## A complete operator

Save the following as a uniquely named file in **Library Management → Operator
directory**, then click **Refresh library**. This example deliberately imports
NumPy inside the computation so metadata can be inspected without running it.

```python
from biopipe_sdk import Operator, Form, port, project_metadata


class Scale(Operator):
    name = "lab.scale"
    version = "0.1.0"
    title = "Scale matrix"
    category = "data"
    # icon = "icons/scale.svg"  # Optional image beside this Python module.
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    input_contracts = [port(ndim=2)]
    output_contract = {"mode": "transform", "representation": "scaled"}
    parameters_schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"factor": {"type": "number", "default": 2.0}},
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
        context.log("Scaling", factor=params["factor"])
        return Form(data=data, dims=list(form.dims),
                    labels={d: dict(v) for d, v in form.labels.items()},
                    info=info, axis_info=axes)
```

Do not mutate input Forms: a branch may reuse them. Preserve or transform
`axis_info` along with the data. `project_metadata` is appropriate for a
shape-preserving derived matrix; selection, transpose and concatenation need
the corresponding Form operations or metadata helpers.

## Declaration reference

| Field | Meaning |
| --- | --- |
| `name`, `version` | Stable namespaced ID and semantic implementation version |
| `title`, `category` | Display name and library category, independent of package origin |
| `icon` | Optional relative PNG/JPEG/WebP/GIF/static SVG, or a known icon name |
| `dependencies` | Literal list of PEP 508 Python requirements, e.g. `scipy>=1.11,<2` |
| `dependency_imports` | Optional module imports used to detect broken native libraries |
| `inputs_arity` | Number of ports, or `"*"` with one repeated input contract |
| `input_contracts`, `output_contract` | Machine-readable data semantics for edges and execution |
| `parameters_schema` | JSON Schema driving validation, defaults and the parameter form |
| `output_parameter` | `"output"` for a dynamic Form name; `None` for report-only Operators |

Missing images use category defaults. Set a category such as `data`, `analysis`,
`quality_control` or `visualization`; custom categories also work. Keep icon paths
relative to the defining module. See [display metadata](operator_protocol.md#operator-categories-and-icons).

## The lower-level Step interface

Implement `run(self, ctx, inputs)`, take parameters from `ctx.step_params`, and
register each declared output as `ctx[output_name] = form`. Return a JSON-compatible
report from `export(self, ctx)`. Use `ctx.log(...)` for structured run messages;
stdout/stderr are also captured. Raise a meaningful exception on failure instead
of silently returning an empty result. Report values must not embed entire input
matrices or huge binary objects.

## Memory and streaming

Override `estimate_memory(cls, inputs, params, profiles)` with temporary workspace
and output byte estimates for the actual algorithm. Estimates guide planning;
emergency spilling remains a fallback. Never claim streaming support just because
the input is memory mapped.

The current `flat-reduction-v1` protocol is for one-input report/reduction Steps:
declare `supports_streaming=True`, `stream_protocol="flat-reduction-v1"`, implement
`run_stream(ctx, stream)`, consume `stream["chunks"]` incrementally and return the
same report through `export`. It is not a generic streaming transform protocol.
[`describe.py`](../src/task/step/steps/describe.py) is a working implementation.
Document numerical tolerances and test streaming versus full execution.

## Test, refresh and distribute

```python
import numpy as np
from biopipe_sdk import Form
from biopipe_sdk.testing import run_operator
from lab_scale import Scale

def test_scale():
    original = np.array([[1., 2.]])
    form = Form(data=original, dims=["sample", "feature"],
                labels={"sample": {"s1": 0}, "feature": {"a": 0, "b": 1}}, info={})
    result = run_operator(Scale, [form], {"factor": 3})
    np.testing.assert_allclose(result.data, [[3., 6.]])
    np.testing.assert_allclose(original, [[1., 2.]])
```

Also test NaN/finite missing sentinels, invalid parameters, metadata propagation
and memory estimates. For a distributable project, use `python -m biopipe plugin
init lab_scale`, then `check`, `test` and `build`; declare wheel dependencies in
`pyproject.toml` as well. A single file can use the class declarations above or
module-level `BIOPIPE_PLUGIN` metadata. See [SDK quickstart](sdk_quickstart.md).

Successful dependency checks last until Studio closes. Only unchecked/failed or
changed implementations are checked after installation/refresh. Conflicting
requirements do not upgrade or downgrade an already-working dependency set.
Use compatible ranges, or report a conflict; automatic import renaming and
multiple incompatible versions in one Python process are not supported.

## Dependency conflicts

Compatible entries share the runtime. Only conflicting entries use a private
dependency directory and subprocess with the same Python executable. See
[selective dependency isolation](dependency_isolation.md) for declarations, streaming,
memory accounting and supported metadata.