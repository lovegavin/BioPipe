# Workflow parameter values

Operator definitions and workflow values have different owners:

| File | Owner | Contents |
| --- | --- | --- |
| `pca.py` | Extension author | Literal definition, contracts and execution code |
| `pca.parameters.json` | Extension author | JSON Schema: types, defaults, constraints and UI hints |
| A route's parameter values JSON | Workflow author | Concrete values for each individual node in that route |
| A route's execution JSON | Workflow author | Memory budgets, placement mode, target assignments and file locations for that version |
| A job's `parameters.json` | Execution record | Concrete values used by one flattened execution |

There is no shared writable parameter-value file for the whole operator library.
Two PCA nodes may have different values, including in two instances of the same
nested route. Changing an extension's schema defaults does not change saved values.

## Save and load

Explicit **Save route** materializes omitted `default` values from the selected
operator/Reader declarations. Explicit `0`, `false`, `null`, empty lists and empty
objects remain unchanged. `x-ui-default` is a new-node editor hint and is never
substituted for a runtime default during saving. For example, PCA currently has
runtime `n_components = 10` and UI preset `2`: an omitted value freezes as `10`,
while a node already set to `2` keeps `2`.

Missing required fields without defaults remain missing so incomplete canvases
can be saved. Running still validates the complete route and its parameters.
Reader defaults are resolved from static suffix/companion metadata, including
TxtReader delegation. Empty or ambiguous source selections remain unresolved until
the user supplies enough information. Internal sources of reusable routes are
interface placeholders; only externally connected sources are read.

The profile stores relative references:

```text
workflows/
  route_0123456789ab.json
  parameters/
    route_0123456789ab/
      v1.json
      v2.json
  execution/
    route_0123456789ab/
      v1.json
      v2.json
  registry.json
```

The saved route record has `parameters_file: "parameters/route_0123456789ab/v2.json"`.
Its `graph` contains structure and implementation pins; concrete `params`, node
`context_params` and Reader `args` live in the referenced JSON. Each nested route
has a separate subtree in that file. Values are written before the route record is
atomically replaced. An interrupted save leaves the previous version usable.
Earlier value files are preserved; optimistic version checks prevent lost edits.
The corresponding `execution_file` references that version's execution sidecar.
Its settings are hydrated together with the values; editing a different workflow
cannot change this route's saved memory or placement configuration.

Opening the route hydrates its values without consulting new defaults. API, CLI,
MCP, editor state and registered route snapshots receive a complete graph, with
values embedded for transport. Re-registering is still explicit. Existing inserted
route instances keep their own complete snapshots.

Saving a modified route creates a new value version. To adopt a new default in an
existing node, edit its value explicitly and save. A library refresh alone never
does this. Existing v2 graph records with inline values remain readable; their next
explicit save creates the separate value file. Draft workspace autosaves retain
their current inline values and do not create route versions.

## Portable route files

**File → Export route bundle** downloads one `.biopipe.zip`, so the user chooses one
destination while keeping three independently inspectable JSON files:

```text
graph.json
parameters.json
execution.json
```

Import the whole bundle through File, the saved-route picker, or
`biopipe graph open route.biopipe.zip --expected-revision <revision>`.
`biopipe graph validate route.biopipe.zip` also accepts the bundle. No archive file
is extracted or executed. Old self-contained graph JSON imports remain supported.
Input datasets, environments and implementation packages are not inside this bundle.
Older two-file bundles remain importable. `execution.json` uses
`format: "biopipe.graph-execution"`, `schema_version: 1`, and `memory`, `execution`
and `routes` objects. Nested-route keys must match the topology. See
[execution settings](EXECUTION_ENVIRONMENTS.md#workflow-settings-and-frozen-json-values)
for target assignment, per-workflow configuration and compatibility behavior.

Graph values use `format: "biopipe.graph-parameters"`, `schema_version: 1`, a global
`params` object and a `nodes` object keyed by node ID. Each node records `kind`,
`operator`, `params`, `context_params`, optional Reader `args`, and optional nested
`route_id`, `route_version`, `route` values. Import checks complete node coverage,
node identity and nesting. A missing, malformed or mismatched sidecar fails clearly;
there is no fallback that quietly replaces it with current defaults.

## Execution records

Every scientific worker job, including jobs triggered through CLI or MCP, writes:

```text
jobs/<job-id>/
  task.yaml
  parameters.json
  plugins.lock.json
  job.json
```

`task.yaml` references `parameters_file: parameters.json` and holds the flattened
execution topology. The JSON has `format: "biopipe.task-parameters"`,
`schema_version: 1`, global `params`, a `sources` map of Reader arguments, and an
ordered `steps` list containing `name`, `inputs`, `params` and `context_params`.
Step identity/order and source coverage must match the task. The worker loads and
validates this pair before execution; the memory planner sees the same actual
values as the operators. Stream processing, disk Readers and memory policy retain
their existing behavior.

A coordinated multi-environment task additionally keeps a parent execution record,
its workflow bundle, stage graphs and child-job references. Each scientific child
uses the worker layout above on its own execution host. Use the workflow bundle
to preserve placement configuration when sharing or reopening a coordinated route.

All sidecar references are relative and constrained to the containing workflow/job
directory. Moving the complete profile or route bundle does not introduce machine
paths. Do not copy `task.yaml` without its parameter file. A raw sidecar-referencing
YAML cannot be imported alone into Studio; import the route bundle instead.

For standalone hand-authored tasks, inline YAML parameters are still supported;
an omitted value in such a task uses that task's selected declaration default.
**Export execution YAML** emits fully materialized inline values as a portable
single-file alternative. To replay a job with `python scripts/run.py <job-dir>`,
keep its `parameters.json`, plugin lock and required datasets together.

Value snapshots protect parameter choices. Implementation pins separately protect
execution identity; `declaration_sha` is an audit field, not a graph matching key.
A compatible default-only update therefore permits importing an old route into a
fresh profile without old registry snapshots. Bundled index fingerprints are also
excluded from graph matching when a v3 `code_sha` is available; exact wheel artifact
digests remain required. Already-created jobs retain and verify their full original
descriptors. See [identity rules](operator_protocol.md#identities-and-updates).
These snapshots do not promise identical results if inputs,
random seeds, external tools or numerical environments change.


## Importing routes from a previous release

As of v0.6.1, a new profile can recognize the exact official v0.5.0/v0.5.1 bundled
implementation identities through the shipped `biopipe/bundled_history.json`.
This is a compact compatibility receipt, not a copy of the old registry or code.
The artifact hash, code hash, package identity, package version and operator
version must match the trusted receipt and current version rules before rebinding.
Third-party wheels and unknown pins still require their original packages.

Preparing a recognized route updates its pins to the selected implementations,
while its separate parameter values remain frozen. Running an unprepared old
route records `bundled_updates` in the new job and logs the rebinding. Existing
job locks and the imported original bundle are never modified. Current parameter
validation still applies; breaking schema/behavior changes require a version bump.
