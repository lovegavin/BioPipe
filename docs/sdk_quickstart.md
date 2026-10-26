# Write an operator in 30 minutes

SDK 3.0 / protocol 3 uses **one implementation plus its own parameter JSON**.
The Python class owns a literal `definition`; its JSON owns parameter types,
defaults, constraints and form hints. The registry is a generated index.

## 0–5 minutes: scaffold

Use the same Python environment as BioPipe:

```text
python -m pip install -e ".[agent,dev]"
python -m biopipe plugin init ./lab_scale
```

The project contains:

```text
lab_scale/
  pyproject.toml
  lab_scale/
    __init__.py         # definition + compute()
    parameters.json    # this operator's JSON Schema
  tests/test_plugin.py
  README.md
```

`biopipe` and `python -m biopipe` are equivalent. No fixed machine path is needed.
For a Reader use `plugin init ./lab_array --template reader`.

## 5–15 minutes: implement and declare

Edit `definition` in `lab_scale/__init__.py`: stable namespaced ID, version, title,
category, input/output contracts, resource capabilities and dependencies. Keep
it literal: the maintenance tool reads the AST without importing your module.
Keep the ID stable when changing the display title.

Edit `parameters.json` for calculation parameters. For example:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "factor": {"type": "number", "default": 2.0, "title": "Scale factor"}
  }
}
```

Use `params["factor"]` in `compute(inputs, params, context)`; the framework supplies
validated defaults. Do not read JSON in each calculation or duplicate defaults in
Python. `x-ui-default` is an optional new-node preset, separate from a runtime
`default`. Existing saved node values are retained.

The generated computation scales a copy and preserves/project metadata. Adapt it
and its memory estimate to the actual algorithm. See the complete examples for
[Steps/Operators](step_extensions.md) and [Readers](reader_extensions.md), and the
[protocol](operator_protocol.md) for field meanings.

Use `definition.category` for grouping. Omit `icon` for a category default, or set
it to a module-relative image such as `icons/scale.svg`. Include JSON and images
in setuptools package data (already configured in the scaffold).

Declare per-operator dependencies in `definition.dependencies`. Common project
requirements apply to every entry. Compatible entries share the environment;
conflicting entries use private dependency directories and subprocesses with the
same Python. See [dependency isolation](dependency_isolation.md).

## 15–20 minutes: check and test

```text
biopipe plugin check ./lab_scale
biopipe plugin test ./lab_scale
```

Checking reads source and JSON without executing imports. It rejects invalid
contracts, schema errors, missing parameters and duplicate/invalid identities.
Tests execute the real runner through `biopipe_sdk.testing.run_operator`.
Add fixtures for missing data, invalid inputs and metadata propagation.
Streaming/disk capability claims must be backed by real implementations; see
[resource protocols](resource_runtime.md).

## 20–25 minutes: build and install

```text
biopipe plugin build ./lab_scale
biopipe plugin install ./lab_scale/dist/lab_scale-0.1.0-py3-none-any.whl
biopipe operators describe example.lab_scale
```

Build returns the exact wheel path. It embeds a generated descriptor, checks
that parameter JSON and icons are present, and validates their contents.
Installation validates dependencies/hooks and precompiles immutable code before
publishing the registry. The open desktop observes the new library. Insert the
operator, wire an input, set parameters, and run explicitly.

Alternatively put the project, built wheel, or a `.py`/parameter-JSON pair into
the folder shown by Library Management and refresh. Copy the entire adjacent
`icons/` directory when the example uses an image. See [hot refresh](plugins.md).

Use the same `--profile-dir` or `--workspace` selector for installation and Studio
when testing in an isolated profile. Normal desktop, CLI and development launches
share the standard data-directory resolver.

## 25–30 minutes: update and share

A parameter-only edit followed by refresh updates descriptors while reusing code,
bytecode and dependency targets. Saved runs retain frozen defaults. Code changes
require installation; increment the package/operator version for behavior changes.
Share the wheel with its README and tests. No central author-maintained JSON is
required. For old extensions, use the explicit [migration](migration_v2.md) before
installing into protocol 3.
