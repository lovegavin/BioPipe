# BioPipe operator library

An independent authoring project for the current protocol-v3 library: 67 operators,
19 Readers and their individual parameter JSON files. No frontend, desktop host,
execution engine, datasets, credentials or user workflows are included.

This project is maintained on the independent
[`library/v1.0.0`](https://github.com/lovegavin/BioPipe/tree/library/v1.0.0) branch.
The matching application source is on
[`release/v0.8.3`](https://github.com/lovegavin/BioPipe/tree/release/v0.8.3).
Keep the checkouts separate; the library branch is an independent source tree,
not a branch to merge into the application or upstream `main`.

```powershell
git clone --branch library/v1.0.0 --single-branch https://github.com/lovegavin/BioPipe.git BioPipe-operators
```

## Layout

- `src/task/step/steps/`: operator implementations, helper modules and parameter JSON.
- `src/reader/readers/`: Readers, streaming/disk preparation hooks and parameter JSON.
- `biopipe/builtin_packages.json`: provider ownership and compiled declaration seed;
  this folder contains metadata, not the application Python package.
- `build_library.py`: statically validate and package the library without starting Studio.

The existing source-relative paths preserve the authoring convention. The builder
rewrites provider imports into private namespaces; installed operators cannot
replace the application's `src` package. Keep code, contracts and actual memory
capabilities aligned. Use stable IDs and declare breaking changes with versions.

## Build and install

Use a Python environment containing BioPipe Studio 0.8.3 or newer. The matching
self-contained Studio distribution includes a usable `runtime/python/python.exe`;
no separate Python installation is required to use that interpreter.

```powershell
python build_library.py --version 1.0.1
```

This produces `dist/BioPipe-Library-v1.0.1.biopipe-library.zip`. In Studio, open
**Operator library management > Import package** and choose that file. No EXE or
frontend replacement is necessary. Or use the matching environment:

```powershell
python -m biopipe plugin install dist/BioPipe-Library-v1.0.1.biopipe-library.zip
```

For live authoring, the application's Operator/Reader folder buttons open its
persistent profile source revision; edit there and click Refresh. This project
is a separate source-release checkout, not an automatically watched directory.
No background scanner changes the active library while files are being edited.

Each operator/Reader keeps its parameters in its own JSON. Saved routes keep
independent parameter values. Package import checks all providers and dependencies
before switching the registry, retains disabled states and older job environments,
and rejects overwriting unrefreshed source edits. Custom standalone wheel packages
retain their separate lifecycle.

The matching Studio distribution contains full English guides in
`docs/step_extensions.md`, `docs/reader_extensions.md`, `docs/operator_protocol.md`
and `docs/plugins.md`.

## Upstream adaptation status

This project contains the tested local library, not the author's newer protocol-1
classes. Upstream commit `9fccadb24624f9fffb8ab756fa730adbb9857fb2` has 80 additional
operator IDs and 24 additional Reader IDs requiring review/adaptation. In particular,
its same-named FastqReader must not replace the file-reference Reader used for Hi-C.
See [the upstream review](UPSTREAM_REVIEW_20261030.md) and
[the exact adaptation inventory](upstream_library_20261030.json).
