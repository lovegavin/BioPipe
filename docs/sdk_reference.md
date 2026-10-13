# BioPipe SDK reference

The supported import surface is `biopipe_sdk`. SDK version is `1.2.0`; protocol
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
with these fields. Exactly one reader must match; ambiguity is an error. For
overlapping formats use distinct suffixes or mutually exclusive sibling requirements.
A complete replacement for `biopipe-readers` replaces that provider's entries,
rather than appending a second set of readers for the same formats.

When `handles_compression` is false, the framework decompresses supported compressed
files before calling `read`; when true, it passes the original path. `parameters_schema`
validates reader `args`, independently of engine-supplied `path`, `dims` and `labels`.
Callers may supply format-specific label modes; support them or reject them clearly.

SDK 1.1 exports `StreamInput`, `SourceProbe` and `DenseDiskWriter` for bounded
execution. The supported hook signatures, admission estimates and ownership rules
are in [package/resource protocol](package_protocol.md). The runnable
`examples/resource_plugin` package uses only public SDK imports.

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

## Studio file import metadata

Readers may declare `file_input` to suggest dimensions, label rules, supported
compression suffixes and required companion filename groups. These fields are
exported in reader descriptors and inspected without loading optional parsers.
See [input formats](input_formats.md#reader-extension-metadata) for the schema and
defaults. Existing readers and plugin descriptors without these hints remain valid.


## SDK 1.2 output inference

`project` can remove `drop_dims`, add `prepend_dims`/`append_dims`, copy axis labels
and derive dimension names from parameters or another input. `choose` selects a
rule by a method parameter. These are serialized declarations consumed equally
by Studio and the runtime, not callable Python hooks. See the examples in
[operator protocol](operator_protocol.md). A backend with SDK 1.2 is required for
these additional rules; an older packaged desktop backend must be updated first.

Use `biopipe registry check` to validate local extension declarations and generated
indexes without starting Studio. New source files with missing schemas/contracts
are reported, not silently converted into permissive plugins.
