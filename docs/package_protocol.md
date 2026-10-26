# Unified packages and resource protocols

Bundled operators and readers are preinstalled packages. They use the same
descriptors, ownership rules, version pins and worker dispatch as installed wheels.
The engine owns execution, contracts, memory admission, spilling and persistence.
Package code owns calculations and format decoding. Routes remain graph-based
operators using their existing snapshot protocol; this change covers Python
operators and readers, not a new route packaging format.

## Preinstalled providers

| Package | Entries | Purpose |
| --- | ---: | --- |
| `biopipe-core` | 30 | Selection, dimensions, concatenation, metadata and describe |
| `biopipe-genetics` | 7 | QC, PCA, regression and correction |
| `biopipe-expression` | 7 | Expression transformations and statistical analysis |
| `biopipe-plots` | 12 | Plots, including survival curves |
| `biopipe-microbiome` | 8 | Abundance diversity, distances, ordination, joins, PERMANOVA, correlation and composition |
| `biopipe-readers` | 15 | File readers, including H5AD and MTX disk preparation |

The startup index is `biopipe/builtin_packages.json`. It enumerates each package's
name, version, title and descriptors. Paths are Python import entry points, never
machine-specific filesystem locations. Use `biopipe registry discover/check/build`
to maintain it together with the route index. `build_builtin_packages.py` builds distributable provider wheels after index maintenance. New modules must declare the complete protocol;
`builtin_package` selects their provider, and existing ownership is preserved.
See [registry maintenance](registry_maintenance.md). Existing operator IDs remain unchanged.

The public package schema is `biopipe_sdk/schemas/package.json`, also available via
`biopipe schema package`. A wheel's embedded `biopipe.json` contains `name`,
`version`, `protocol_version`, `origin`, `dependencies` and `descriptors`. Protocol version is exactly 2; no `package` alias is accepted. Standard wheel metadata remains the
authority for pip dependencies, and manifest identity must match wheel metadata.

## Management and hot replacement

Studio's **算子库管理** lists both bundled and wheel providers, their entries and
resource modes. Installation/update accepts a local wheel. Enable, disable, remove
and restore publish a new registry generation without restarting the application.
The primary **Refresh library** action also discovers changes directly in the normal
operator/Reader directories. Authors need only save their Python modules; scanning,
protocol validation and immutable provider packaging happen internally. See
[whole-library refresh](plugins.md#drop-refresh-use).

```bash
biopipe plugin list
biopipe plugin disable biopipe-genetics
biopipe plugin enable biopipe-genetics
biopipe plugin remove biopipe-genetics
biopipe plugin restore biopipe-genetics
```

Disable/remove applies to new unpinned graphs. Prepared, saved or launched graphs
retain their implementation locks and can resolve an older available generation.
Removal unregisters a provider; it does not delete historical wheels/environments.
Restoring a bundled package replaces its installed wheel with the shipped provider.
Running workers continue unchanged. Old registries require [explicit migration](migration_v2.md). A
bundled-provider receipt adds newly shipped packages without resurrecting removed
providers or overriding disabled/wheel-installed packages.

To produce an independently installable version of a bundled provider:

```bash
python scripts/build_builtin_packages.py --refresh
python scripts/build_builtin_packages.py --package biopipe-readers --output build/packages
biopipe plugin install build/packages/biopipe-readers/dist/biopipe_readers-1.0.0-py3-none-any.whl
```

Choose a fresh build output directory each time. Bump the package version in the
index before publishing an update. The builder copies implementation modules into
a provider-specific namespace, so a wheel does not overwrite `src` or another
environment's code. Bundled package names own their established IDs. A replacement must
retain all those IDs; unrelated packages cannot shadow them. This is ownership
validation, not a signature or publisher authentication scheme: install trusted wheels.
Third-party IDs remain namespaced, such as `lab.scale`.

Bundled pins include a content fingerprint. New runs reconcile known bundled source updates within protocol v2 and record
the effective fingerprints. A worker refuses code changed after its job was prepared. To keep historical implementations executable across application upgrades,
use versioned wheels and retain their generations. Native/optional reader libraries
still require the appropriate runtime environment (`requirements-readers.txt`);
bundled wheels do not bundle those libraries or an interpreter.

## `flat-reduction-v1`: stream operators

Declare `supports_streaming = True` and `stream_protocol = 'flat-reduction-v1'`.
This contract supports one numeric input and report-only output (`report` or `none`),
with no Form outputs. Implement `run_stream(ctx, stream)` as well as equivalent
`run(ctx, inputs)` for memory-management-disabled execution.

`StreamInput` contains `shape`, `metadata` (`dims`, `labels`, `info`, `axis_info`),
and `chunks`. Chunks are a single-pass iterator over bounded, one-dimensional
C-order numeric blocks. Boundaries need not align with matrix rows. Treat chunks
as read-only and release references before requesting another; do not concatenate
or retain all chunks. The runner owns iterator cleanup and validates consumed values.
Column-specific operations and multiple-input joins need a different protocol;
declaring this mode does not make them streamable.

`stream_buffer_multiplier` is a positive integer (default 4), and
`stream_fixed_bytes` is a nonnegative integer (default 0). The planner reserves:

```text
metadata reserve + stream_fixed_bytes
  + chunk_elements * (max(dtype.itemsize, 8) * stream_buffer_multiplier + 1)
```

The multiplier counts estimated temporary buffers in addition to input handling.
Declare enough space for the implementation; it is an estimate, not a hard RSS
guarantee. Available memory is still sampled once before the run. This protocol
preserves builtin `describe` and is available to third-party wheels identically.

## `dense-writer-v1`: disk readers

Declare `supports_disk_read = True` and `disk_protocol = 'dense-writer-v1'`.
Implement all three methods:

* `read(path, dims, labels, **args) -> Form`: equivalent eager fallback.
* `probe(path, **args) -> SourceProbe`: metadata-only shape, dtype, file bytes,
  dense bytes and temporary-plus-output disk bytes (`preparation_bytes`).
* `read_to_disk(path, dims, labels, writer, chunk_bytes, **args) -> dict`:
  bounded decoding into the supplied writer; return Form metadata without `data`.

Probe shape is two nonnegative integer dimensions; dtype is fixed-width real
numeric. `dense_bytes` must equal `product(shape) * dtype.itemsize`; preparation
space must include temporary accumulators. File bytes are recorded with `stat`,
independently of expanded size. Invalid probes fail before allocation.

Use `writer.write(row, column, values)` for contiguous row segments or
`writer.add(row, column, scalar)` for accumulation. Positions are bounds-checked.
The framework creates, flushes, validates and atomically commits the NPY file;
plugins must not close/replace the supplied writer or retain its buffers. The writer
handles bounded caching and emergency spills. Readers must also keep their parser
buffers within `chunk_bytes` and account for additional temporary storage.

Returned metadata contains `dims`, `labels`, `info` and `axis_info`. Structural
and metadata contracts are checked without allocating a full dense array. Declared
reader value constraints are checked against actual staged blocks and cover the
entire matrix. Compression wrapping applies to `probe` and `read_to_disk` as it
does to `read`; readers handling compression themselves receive the original path.

After staging, the runtime retains eligible clean blocks and releases only the
amount required by operator admission. No full-array concatenation is introduced.
H5AD dense/CSR/CSC/layers and MTX duplicate/symmetric handling keep their existing
implementations under this public protocol.

## Executable example

`examples/resource_plugin` provides a NumPy disk reader and a streaming sum operator
using SDK-only imports. Build/install it with the ordinary developer commands:

```bash
biopipe plugin check examples/resource_plugin
biopipe plugin build examples/resource_plugin
biopipe plugin install examples/resource_plugin/dist/biopipe_resource_example-0.1.0-py3-none-any.whl
```

The integration tests build real wheels, install them into new generations and run
fresh workers, covering builtin replacement, H5AD/MTX disk staging, streaming,
compressed external-reader input, old locks, and enable/remove/restore behavior.
