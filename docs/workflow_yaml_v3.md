# Author workflows in YAML

Operon 3.0 accepts `operon.workflow` schema version 1. This is an authoring
format, not a new execution engine: it compiles into the same Graph used by
Studio, the application API and MCP. Existing graph JSON and route ZIP remain
accepted.

In Studio, put the complete YAML project inside the selected workspace and set
the import dialog's **base directory** to the folder containing the YAML, JSON
sidecars and scripts. Importing a YAML file alone cannot upload its neighboring
files. A complete workflow ZIP is another supported transfer method. CLI import
resolves sidecars relative to the YAML file automatically. Missing, unreadable or
malformed sidecars return a validation error naming the file and expected project
directory; correct the location or file and retry. Failed imports do not modify
frozen values or start a task.

```sh
operon workflow init ./analysis --template csv-pca
operon workflow lint ./analysis/workflow.yaml
operon workflow format ./analysis/workflow.yaml --check
operon workflow prepare ./analysis/workflow.yaml --format yaml --output ./prepared
operon workflow validate ./prepared/workflow.yaml --require-files
operon run ./prepared/workflow.yaml --wait
```

`init`, `lint`, `format`, `schema workflow` and script inspection run without a
service, desktop or scientific imports. Prepare, target validation and execution
use the shared application API. Lint does not prove that operators, files or
dependencies exist on the execution target. Format normalizes YAML and may remove
comments; `--check` writes nothing and exits 1 if formatting differs.

```yaml
format: operon.workflow
schema_version: 1
name: PCA branches
parameters_file: parameters.json
execution_file: execution.json
sources:
  matrix:
    path: data/matrix.csv
    dims: [sample, feature]
    labels: {sample: auto, feature: builtin}
steps:
  pca_main:
    operator: pca
    inputs:
      in0: sources.matrix
  pca_other:
    operator: pca
    inputs:
      in0: sources.matrix
outputs:
  scores: steps.pca_main.out
```

The IDs `pca_main` and `pca_other` identify separate instances of the same operator.
Input ports use `in0`/`in-0`, `in1`/`in-1`, etc.; outputs use `out`, `out-0`, etc.
The aliases refer to numeric ports of existing operators, not inferred semantic
names. Unknown references, duplicate keys or ports, cycles, YAML tags and aliases
are rejected. The loader treats `on` and `off` as strings and `true`/`false` as
booleans. The scalar syntax is intentionally conservative; prefer decimal numbers
and explicit strings in hand-authored documents.

`parameters.json` owns values, not schemas or library defaults:

```json
{
  "format": "operon.workflow-parameters",
  "schema_version": 1,
  "sources": {"matrix": {"args": {}}},
  "steps": {
    "pca_main": {"params": {"n_components": 2}},
    "pca_other": {"params": {"n_components": 3}}
  }
}
```

`execution.json` carries existing memory and execution configuration without
inventing a second scheduler configuration:

```json
{
  "format": "operon.workflow-execution",
  "schema_version": 1,
  "memory": {"enabled": true, "auto_spill": true},
  "runtime": {}
}
```

Omitting `budget_mb` retains the host's automatic budget policy. Parallel nodes do
not each receive a separate 90% host budget. Existing manual/automatic placement
configuration lives under `runtime.execution` and keeps its application semantics.

Inline `parameters` or `execution` can replace their corresponding sidecar
reference, but cannot coexist with it. Prepare/export freezes selected defaults
through the existing application service; explicit zero, false, null and empty
values survive. Export writes separate parameters, execution, implementation lock
and UI position files, and refuses to overwrite a nonempty directory. Nested route
definitions and their parameter subtrees are retained.

Local source and sidecar paths resolve relative to the YAML document, never the
shell's current directory. Remote source paths retain the server namespace. Server
read-root authorization still applies; YAML does not grant new filesystem access.
Metadata sidecars, locks, UI files and referenced scripts must use relative paths
contained in the project directory; symlinks escaping it are rejected. Input data
may use authorized external absolute paths.
Graph-to-project export preserves already-authorized input paths rather than
copying data. Moving a project requires updating any external input locations.

Edge bindings can preserve converter selection and stable edge IDs:

```yaml
inputs:
  in0:
    from: sources.matrix
    id: matrix_to_pca
    adaptation:
      mode: auto
      converters: []
```

The conversion planner decides compatibility. YAML never converts matrix semantics
into lists just because a representation can be serialized. Scientific conversions
remain explicit nodes. The workflow `outputs` mapping records named output
references; artifact publication continues through the shared output service.

Use `operon schema workflow` for the authoring structure schema. Library schemas,
runtime contracts and target readiness add validation beyond that structure.

## Scripts and independent exports

The desktop file menu can export an **editable YAML project** ZIP. Its five files
keep topology, values, execution settings, pins and layout separate. Import that
ZIP through the same workflow menu. For a YAML file with sidecars already inside
the workspace, set its input directory before import. The older **execution YAML**
export remains available for the low-level task runner.

See the [synthetic branched script example](../examples/workflows/script_pipeline/README.md)
for a small standard-library-only workflow and the imported-default behavior.

See [Script operators](script_operators_v3.md) for code import, parameter binding
and file-process execution, and [Portable packages](portable_packages_v3.md) for
the currently verified standalone subset. Unsupported implementations fail
explicitly; native scientific operators are not automatically translated.
