# Write a BioPipe plugin in 30 minutes

This walkthrough assumes a working BioPipe Python environment and an existing
small algorithm. It scaffolds a real wheel, tests contracts, hot-installs it and
makes it available in the desktop. BioPipe does not need an AI provider.

## 0–5 minutes: prepare the development environment

From the BioPipe repository, using the same Python environment as Studio:

```text
python -m pip install -e ".[agent,dev]"
python -m biopipe --help
```

If pip is unavailable, use `uv pip install --python <interpreter> -e ".[agent,dev]"`.
The package is supplied by this repository; these instructions do not assume a
published PyPI release. `biopipe` is a console entry point; `python -m biopipe`
performs the same operation when the executable is not on PATH.

Start Studio by double-clicking its desktop executable or running
`python scripts/studio.py`. Keep the usual profile to share its registry.

## 5–15 minutes: scaffold and implement

```text
biopipe plugin init ./lab_scale
```

The generated project contains `pyproject.toml`, `lab_scale/__init__.py`, a README,
and `tests/test_plugin.py`. It exposes `example.lab_scale` through the
`biopipe.operators` entry-point group. Replace `example` with your stable namespace
before sharing the plugin.

The generated implementation includes:

```python
import numpy as np
from biopipe_sdk import Operator, Form, port, project_metadata

class Scale(Operator):
    name = "my_lab.scale"
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
        info.update(representation="scaled", missing_code=float("nan"))
        context.log("Scaling matrix", factor=params["factor"])
        data = form.data.astype(float, copy=True)
        missing = form.info.get("missing_code")
        if missing is not None:
            data[data == missing] = np.nan
        data *= params["factor"]
        return Form(data=data, dims=list(form.dims),
                    labels={d: dict(v) for d, v in form.labels.items()},
                    info=info, axis_info=axes)
```

Use input dimensions rather than assuming the sample axis is always axis 0.
The example converts a finite missing sentinel such as `-9` to NaN before scaling,
and preserves existing NaNs.
Declare any additional pip dependencies in the plugin's `pyproject.toml`.
The generated memory estimate should be adjusted for your algorithm.

Choose `quality_control`, `analysis`, `data` or `visualization` for the library
category, or use your own label. `kind` is inferred from the base class; do not
set it to a category name. An omitted category uses the Uncategorized group.
An omitted or unknown icon name uses the default icon. See the
[display metadata reference](operator_protocol.md#operator-categories-and-icons)
for the available names. The generated template includes these optional fields.

## 15–20 minutes: check and test

```text
biopipe plugin check ./lab_scale
biopipe plugin test ./lab_scale
```

`check` returns the public JSON descriptor and rejects missing contracts, invalid
schemas or unnamespaced IDs. `test` runs the project's pytest tests. The template
uses `biopipe_sdk.testing.run_operator` to exercise the actual runner, parameter
validation and output contracts, and checks that the original input was unchanged.
Add a missing-data fixture and an invalid-input case for your real algorithm.

## 20–25 minutes: build and hot-install

```text
biopipe plugin build ./lab_scale
biopipe plugin install ./lab_scale/dist/lab_scale-0.1.0-py3-none-any.whl
biopipe plugin list
biopipe operators describe example.lab_scale
```

Use `my_lab.scale` in the last command if you changed the namespace. The build
returns the exact wheel path and generated manifest. Installation resolves a new
environment generation and publishes the registry only after validation succeeds.
An open Studio refreshes its library within approximately five seconds. Search for
“Scale matrix”, insert it, wire a numeric input, set the factor and run explicitly.

With an isolated workspace, use the same selector for Studio and installation:

```text
python scripts/studio.py --workspace ./my-workspace
biopipe --workspace ./my-workspace plugin install ./lab_scale/dist/lab_scale-0.1.0-py3-none-any.whl
```

`--profile-dir` selects a complete profile instead. Default desktop, development
server, CLI and MCP all use the same resolver; no machine path is embedded.

## 25–30 minutes: share and version

Share the wheel, README and source tests. Increment package/operator versions when
you change behavior. Rebuild and install to publish a new version; existing saved
graphs keep their previous implementation pins. Removing a plugin hides it from
new insertions while retaining historical environments for pinned routes:

```text
biopipe plugin remove lab-scale
```

Native libraries must be built for the target platform. Plugin code runs with the
user's permissions; installation isolation protects dependencies, not the OS.

## Reader template

```text
biopipe plugin init ./lab_array --template reader
biopipe plugin check ./lab_array
biopipe plugin test ./lab_array
biopipe plugin build ./lab_array
biopipe plugin install ./lab_array/dist/lab_array-0.1.0-py3-none-any.whl
```

This template loads numeric `.npy` files with `allow_pickle=False`, accepts exactly
two supplied dimension names and supports automatic labels or explicit name-to-
position maps. Unsupported label modes fail explicitly. It declares
`reader_contract()` and an empty parameter schema. Add a data source with the new
extension; normal reader selection, output validation and worker execution apply.
Readers must return complete labels and truthful metadata before registration.

For the full API and resource limitations, see [SDK reference](sdk_reference.md)
and [protocol](operator_protocol.md).
