# Add a Reader

A Reader converts files into a `Form`: numeric data, named dimensions, labels,
global `info` and dimension-aligned `axis_info`. Reader discovery, dependencies,
contracts and installation use the same protocol as Steps.

## Minimal source extension

Open **Library Management → Reader directory**, add a uniquely named `.py` file,
then click **Refresh library**. Use the path shown by Studio; do not hard-code
the release folder or a developer's home directory. A complete project can also
be generated with `python -m biopipe plugin init lab_reader --template reader`.

This example reads NumPy arrays without allowing pickled objects:

```python
from biopipe_sdk import Reader, Form, reader_contract


class NpyReader(Reader):
    name = "lab.npy"
    title = "NumPy matrix"
    version = "0.1.0"
    extensions = [".npy"]
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    parameters_schema = {"type": "object", "additionalProperties": False}
    output_contract = reader_contract()

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
        return Form(data=data, dims=list(dims), labels=mapping,
                    info={"missing_code": float("nan")})
```

Keep third-party imports inside methods when possible: discovery should not need
to execute the actual parser. Literal class `dependencies` are read before source
imports, installed in a candidate environment, then validated before publication.
Names such as `scikit-learn` are distribution names; `dependency_imports` uses
import names such as `sklearn`. Use PEP 508 version ranges and platform markers.
For wheel projects, also list dependencies in `[project].dependencies` so pip
can install them before loading your entry point.

## File selection and metadata

Declare `requires_siblings` and `excludes_siblings` for file groups, and
`file_input` for Studio's named file slots; see [input formats](input_formats.md).
Declare `handles_compression=True` only when the parser consumes compressed files
itself. Otherwise the framework handles its supported compression wrappers.
Never claim a format if a required sidecar cannot be validated.

`info` describes the whole dataset, for example missing values or representation.
`axis_info[dimension][field]` holds annotations aligned with that dimension. Every
annotation vector must have the correct axis length. Do not hide axis-aligned
vectors in arbitrary global metadata and expect downstream filtering to update them.
Use contracts to advertise semantic guarantees; extensions alone are insufficient.

## Disk reads and bounded preparation

For large data, implement all three pieces together:

```python
supports_disk_read = True
disk_protocol = "dense-writer-v1"

def probe(self, path, **args):
    # Read only the format's header/index to obtain shape and dtype.
    # Return file_bytes, shape (2D), dtype, dense_bytes and preparation_bytes.
    ...

def read_to_disk(self, path, dims, labels, writer, chunk_bytes, **args):
    # Decode bounded chunks; writer.write(row, column, values) writes a row slice.
    # Return {"dims": ..., "labels": ..., "info": ..., "axis_info": ...}.
    ...
```

`dense_bytes = product(shape) * dtype.itemsize`; `preparation_bytes` must also
include temporary disk storage. File size alone is not the decoded memory size.
Use `Path(path).stat().st_size` to obtain file size without reading the file.
Use the supplied writer so preparation participates in emergency spilling. Do not
collect all chunks and concatenate them at the end. Existing examples include
[`mtx_reader.py`](../src/reader/readers/mtx_reader.py) and
[`h5ad_reader.py`](../src/reader/readers/h5ad_reader.py).
See [resource protocol](resource_runtime.md) for its exact supported boundaries.

## Test and register

Test a tiny valid file, missing sidecars, invalid shape, labels, missing values,
and contract metadata. Compare normal and disk reads numerically and verify
chunk memory stays bounded. For the NPY example:

```python
import numpy as np
from lab_reader import NpyReader

def test_read(tmp_path):
    path = tmp_path / "matrix.npy"
    np.save(path, np.array([[1., 2.], [3., 4.]]))
    result = NpyReader().read(path, ["sample", "feature"], {})
    assert result.data.shape == (2, 2)
    assert result.labels["sample"] == {"0": 0, "1": 1}
```

Refresh the library and inspect the Reader's dependency status. A failed refresh
preserves the previous catalog. Source maintainers can run
`python -m biopipe registry check` and `python -m biopipe registry build` to publish
the checked-in manifest. A user's desktop refresh updates its profile registry,
not the source repository. See [SDK quickstart](sdk_quickstart.md) for wheels.

## Dependency conflicts

Compatible entries share the runtime. Only conflicting entries use a private
dependency directory and subprocess with the same Python executable. See
[selective dependency isolation](dependency_isolation.md) for declarations, streaming,
memory accounting and supported metadata.
