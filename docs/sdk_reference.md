# BioPipe SDK reference

The supported import surface is `biopipe_sdk`. SDK version is `1.0.0`; protocol
version is `1`. The SDK currently ships with the `biopipe-studio` distribution.

| Export | Use |
| --- | --- |
| `Operator` | Implement `compute(inputs, params, context)` for one Form or a report |
| `Step` | Compatible advanced API: `run(ctx, inputs)`, `export(ctx)` and fixed outputs |
| `Reader` | Implement `read(path, dims, labels, **args) -> Form` |
| `Form` | Numeric tensor with named dimensions, labels, `info` and `axis_info` |
| `Context` | Current step parameters, Form registry, outputs and logging |
| `port`, `param`, `MISSING` | Input contract constructors and parameter references |
| `reader_contract` | Standard output declaration for a reader |
| `project_metadata`, `concat_metadata` | Metadata propagation helpers |
| `StepError`, `ReaderError` | Actionable calculation/reading failures |

## Context

- `context.step_params`: validated parameters plus engine fields. `Operator.compute`
  receives only calculation parameters through its `params` argument.
- `context[name]`: access a named Form; assignment validates and registers a fresh
  output. Prefer the return-value API for a single output.
- `context.log(message, **fields)`: emit an `operator_log` event and console log.
  Fields should be JSON-compatible summaries, not full matrices or secrets.
- `context.artifact_path(name)`: obtain a path under the run output's `artifacts`
  directory. Parent traversal and paths escaping this directory are rejected.
  Write a file there and return its path in the report.
- `context.out_dir`: run output directory, for legacy code requiring the existing
  report/figure layout.

The runner creates a new instance per execution, calls `run`, then calls `export`.
Raise a clear exception on unsupported input; do not silently change an algorithm
or fill missing biological semantics. Failures appear in job logs and summaries.

## Reader dispatch

Set `extensions` to suffixes such as `[".npy"]`. Optional `requires_siblings` and
`excludes_siblings` describe companion files. Implementing arbitrary custom
`matches()` logic is outside the static desktop contract: make routing describable
with these fields. The first matching reader wins; do not use a plugin to override
a built-in extension. For overlapping plugin formats use distinct suffixes or
mutually exclusive sibling requirements.

When `handles_compression` is false, the framework decompresses supported compressed
files before calling `read`; when true, it passes the original path. `parameters_schema`
validates reader `args`, independently of engine-supplied `path`, `dims` and `labels`.
Callers may supply format-specific label modes; support them or reject them clearly.

## Metadata helpers

```python
info, axes = project_metadata(form,
    selections={"feature": indices},
    keep_dims=["sample", "feature"],
    rename={"feature": "gene"},
    derived=False)
```

Selections are integer positions applied identically to the data, labels and axis
annotations. The helper only computes metadata: the caller slices the tensor and
rebuilds label positions. `keep_dims` drops annotations on reduced axes; `rename`
renames dimension bindings and encoder references. `derived=True` removes invalid
genotype/alphabet semantics and encoders for transformed data columns. It preserves
valid retained annotations. Some unmodified metadata values may be shared; copy a
value before mutating it.

`concat_metadata(forms, axis)` assumes forms have already been aligned. It merges
axis annotations, fills missing concatenated annotations with null, and rejects
conflicting aligned metadata, encoders or missing markers. It does not align tensors.

## Testing

```python
from biopipe_sdk.testing import run_operator
output = run_operator(MyOperator, [small_form], {"factor": 3})
```

This helper executes the real runner with contract checks in a temporary output
directory. It is intended for small CPU fixtures and returns the Form or report.
It temporarily registers the class in the process's operator map; do not call it
concurrently from threads. Use separate pytest processes for parallel tests.
Use Studio job tests to verify persistent artifacts, resource limits, installed
dependencies and historical plugin versions.

Memory estimates and descriptor fields are defined in the
[operator protocol](operator_protocol.md). There is no general public chunk or GPU
allocator API in v1; native full-memory operators cannot be preempted mid-allocation.
