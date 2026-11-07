# Logical types and representation adaptation

SDK 3.7 requires explicit `data_formats` on new revision-3.7 declarations. Both
input and output arrays must be present, even when empty. SDK 3.6 introduced
these capabilities as optional; the base protocol remains 3. Existing v3,
v3.5 and v3.6 declarations retain their existing
contract path. New capabilities do not infer scientific semantics from extensions,
array dimensions or Python coercions.

## Declare both layers

An operator's literal `definition` can include:

```python
"protocol_revision": "3.7",
"data_formats": {
    "inputs": [{
        "logical_type": "matrix",
        "representations": ["numpy.ndarray", "npy.memmap"],
        "metadata": {"dtype": "float32"}
    }],
    "outputs": [{
        "logical_type": "matrix",
        "representations": ["numpy.ndarray"],
        "metadata": {"dtype": "float32"}
    }]
}
```

For an existing Form interface, declare `logical_type: "form"` and
`representations: ["form"]`. For a file-backed interface use
`logical_type: "file_artifact"` and `representations: ["file_artifact"]`.
These container contracts do not assert a scientific matrix/list interpretation.
The legacy port default `kind: "form"` remains a protocol guarantee; explicit
`kind: ["form", "file"]` is polymorphic and cannot be narrowed automatically.
See [static migration](format_migration_v37.md) for inspect/apply commands.

## Native Reader to Form bridge

A Reader may declare `logical_type: "form"` with
`representations: ["native.ndarray"]` and return the SDK's `NativeArray`:

```python
from operon_sdk import NativeArray
payload = NativeArray(array, ["sample", "feature"], labels,
                      {"missing_code": float("nan")}, axis_info)
```

`array` must be an actual NumPy ndarray (including a memory map), and dimensions,
labels, info and axis_info must be provided explicitly. Reader ingestion validates
and wraps this payload without copying its data; `form.ndarray.wrap` is the
registered adaptation. A Reader already returning Form keeps the same object.
This does not turn arbitrary FASTQ/BAM/VCF files into matrices: file artifacts
still require a registered parser or a scientifically meaningful operator.

Run the [native Reader example](../examples/sdk37_native_reader/README.md) to
verify a mapped NPY, metadata-preserving Form bridge and unchanged legacy
`log_transform` operator. No library migration or external data is needed.

Keep the existing `contracts` declaration. It describes axes, annotation fields,
value constraints and transformations. `data_formats` adds logical type and
physical representation requirements, rather than replacing those checks.
Readers declare zero inputs and one output. Variable-arity operators declare one
input capability reused for their inputs. Each actual output must resolve to one
representation; multiple unresolved output choices block preparation rather than
silently demanding a format that the implementation does not produce.

Metadata requirements use exact values. `dims`, `shape` and `dtype` refer to the
actual Form; other fields refer to `info`. Missing metadata is unknown, not a
wildcard. A matrix cannot feed a logical list even if both use an ndarray. Insert
an explicit scientific conversion operator to select rows, columns, flattening,
aggregation or another intended meaning.

## Edge policies and diagnostics

An edge may contain `adaptation`:

```json
{"mode": "auto", "converters": []}
```

Use `disabled` to require direct compatibility, or `fixed` with an explicit
converter ID chain. Other mode/chain combinations are rejected. The contract API
returns a `conversion_plan` containing source/target contracts, selected
representation, converter IDs, versions, code identities and dependencies. The
canvas displays a small conversion marker with the chain on hover. Unknown format
requirements cannot be submitted as ready.

Search is deterministic, acyclic and bounded to four conversions, 128 candidate
converters and 256 explored states. These are planner-complexity limits, not input
file size limits. Direct compatible connections do not perform conversion.

## Initial executable conversions

The first verified registry includes:

| ID | Source | Target | Behavior |
| --- | --- | --- | --- |
| `matrix.npy.write` | `numpy.ndarray` | `npy.memmap` | Bounded numeric NPY writes, then readonly mapping |
| `matrix.npy.view` | `npy.memmap` | `numpy.ndarray` | Readonly ndarray view over the mapping; no full copy |

Numeric values, dtype, axes, labels, `info`, `axis_info` and missing-value metadata
are retained. Object arrays are refused. Kernels write via a temporary file and
publish only after flushing; cancellation removes incomplete files. Conversion
buffers and scratch are admitted against the existing managed RAM and disk
budgets, and conversion events appear in the run log. Managed storage may already
provide the required mapping, in which case it is reused.

The initial registry is application-owned; arbitrary converter code is not loaded
from a user-supplied plan. Runtime checks the frozen identity against registered
implementations. Additional Arrow/Parquet, sparse, compressed and domain codecs
require separate implementation and losslessness tests before becoming automatic.
This implementation does not claim universal conversion or a completed third-party
converter package installer. A mutable input is not shared across conversion cache
entries based merely on its filename. Conversion scratch is retained within its
run directory and quota; cross-run conversion-cache reuse is not yet enabled.

Readers continue to parse and expose source data. They are not asked to eagerly
create every representation a consumer might request. The existing streaming
Reader and emergency-spill protocols remain unchanged. Full-Form converters are
not applied to a streaming reduction input; such a mismatch fails explicitly.

## Execution and standalone export

The graph compiler emits frozen per-input `conversions` in executable steps.
The common runner applies them before the existing input-contract validation.
Both the graph and its execution plan are required for diagnostics; the badge is
not the execution mechanism.

The NPY kernels in `operon/converter_kernels.py` depend only on NumPy and Python's
standard library. A portable exporter can include this module, locked NumPy,
sidecar metadata and the actual invocation. It must validate the complete converter
closure; an exporter that cannot include a converter must reject the workflow.
Copying only visible scientific nodes is not a valid standalone export.

See `tests/test_format_adaptation.py` for numeric/metadata round-trips, bounded
search, policy errors, actual runner execution, cancellation and an independent
kernel subprocess without Operon imports.
