# Add a Reader

Readers use the same code + per-Reader parameter JSON protocol as operators.
Save this implementation as `npy_reader.py`:

```python
from biopipe_sdk import Reader, Form

class NpyReader(Reader):
    parameters_file = "npy_reader.parameters.json"
    definition = {
        "protocol_version": 3, "id": "lab.npy", "version": "0.1.0",
        "kind": "reader", "title": "NumPy matrix", "extensions": [".npy"],
        "contracts": {"version": 1, "inputs": [],
                      "output": {"numeric": True, "ndim": 2}},
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.26"], "dependency_imports": ["numpy"]
    }

    def read(self, path, dims, labels, **args):
        import numpy as np
        data = np.load(path, allow_pickle=False)
        if data.ndim != 2 or len(dims) != 2 or data.dtype.kind not in "biuf":
            raise ValueError("Expected a 2D real numeric array and two dimension names")
        mapping = {}
        for dim, size in zip(dims, data.shape):
            spec = labels.get(dim, "auto")
            if spec == "auto":
                mapping[dim] = {str(i): i for i in range(size)}
            elif isinstance(spec, dict):
                mapping[dim] = dict(spec)
            else:
                raise ValueError("Use auto labels or an explicit name-to-position map")
        return Form(data, list(dims), mapping, {"missing_code": float("nan")})
```

Save `npy_reader.parameters.json` beside it (even a Reader with no options has an
explicit empty schema):

```json
{"type": "object", "properties": {}, "additionalProperties": false}
```

Add both files through the Reader directory and refresh. Alternatively,
`biopipe plugin init lab_reader --template reader` generates a complete project.
The file picker, contracts and worker all use the same generated descriptor.

Put suffixes, `requires_siblings`, `excludes_siblings`, `handles_compression` and
optional `file_input` hints in `definition`. The framework selects a Reader without
importing its implementation. Compression handling remains centralized: Readers
without native compression receive a temporary decompressed file. Use the existing
format helpers; do not remove compression suffixes independently in the frontend.

Reader schema defaults are materialized into the route's independent value JSON
when a source can be resolved. Later default edits do not alter saved Reader
arguments. Use the supplied arguments rather than rereading the author's JSON at
execution time. See [workflow parameter values](workflow_parameters.md).

A large-file Reader can provide `probe()` and `read_to_disk()` and declare
`resources.memory_modes = ["full", "disk"]` and `disk_protocol = "dense-writer-v1"`.
`probe` reads metadata, never eagerly densifies payloads. `read_to_disk` writes bounded
blocks via the engine writer, preserving disk admission and emergency spilling.
See the [resource protocol](resource_runtime.md) and
[NPY disk Reader example](../examples/resource_plugin/resource_example/__init__.py).

Set `info` and `axis_info` consistently with dimensions and labels. Report optional
parser dependencies using distribution names in `dependencies` and import names in
`dependency_imports`. Compatible dependencies share the runtime; conflicts run with
private dependency directories and an independent process using the same Python.

## File-backed Reader example

For large disk datasets, the Hi-C Readers demonstrate metadata-only loading:
`src/reader/readers/fastq_reader.py` declares the file contract and
`fastq.parameters.json` owns the mate-path and quality-encoding schema. Runtime
returns `FileArtifact`, and `sequence_stats` consumes it record by record. The
existing numeric Reader disk protocol and streaming methods are unchanged.
See [SDK file datasets](sdk_reference.md#file-backed-datasets) and [Hi-C](HIC.md).
