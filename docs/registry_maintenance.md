# Registry maintenance

BioPipe loads checked-in JSON indexes at startup. It does not repeatedly scan
source folders or fetch GitHub while the user edits a canvas. Maintainers use one
explicit discover/check/build workflow; plugin wheel installation remains a
separate, hot-install operation. For **live operator library updates**, the
operator library's refresh button scans the application's existing operator/Reader
source directories and the shared profile's additional folder. It validates changed
source modules, wheel or project inputs and atomically updates the live
registry. See [library hot refresh](plugins.md#drop-refresh-use). The commands
below maintain the repository indexes and are not required for local hot refresh.

Run these commands from a source checkout with its Python environment installed:

```bash
python -m biopipe registry discover
python -m biopipe registry check
python -m biopipe registry build
python -m biopipe registry check
```

`biopipe registry ...` is equivalent when the CLI is on PATH. No running Studio,
desktop host, datasets, profile migration or fixed machine path is required.

## What each action does

| Action | Reads | Result | Writes |
| --- | --- | --- | --- |
| `discover` | Python AST and route YAML | JSON inventory, indexed/new IDs, route dependencies | None |
| `check` | Trusted local extension declarations and route definitions | Protocol errors and indexes that would change | None |
| `build` | Same validated candidate as `check` | Operator/Reader package index and route graph interfaces | Changed index files only |

`check` exits with code 1 when a declaration is invalid **or** a generated index
is stale; otherwise it exits 0. `build` exits 1 on failure. Validation of all
selected indexes finishes before any index is replaced. Errors include the source
path. A failed validation leaves existing indexes intact. Each successful file
replacement is atomic and builds are serialized by a maintenance lock. The two
files are not a single crash-atomic filesystem transaction; rerunning `build`
repairs an interrupted publication.

Repeated builds without source changes write nothing. Output is JSON for CI and
external agents. A fresh maintenance process bypasses the startup index so that a
missing or stale entry point does not prevent source repair.

```bash
# Preview generated artifacts outside the source indexes:
python -m biopipe registry build --output-dir .tmp/registry-preview
# Discover additional route roots (repeat the option to combine roots):
python -m biopipe registry check --route-root routes --route-root extra_routes
# Compatibility commands; use the unified build for complete validation:
python scripts/build_builtin_packages.py --refresh
python scripts/build_builtin_routes.py
```

`--scope packages` or `--scope routes` limits generated files. Extension validation
still runs in either scope, because routes depend on valid operator declarations.
Checking an alternate output directory compares the candidate against that
directory. These are repository maintenance commands, not commands for editing
the user's active plugin registry.

## Adding an operator or Reader

1. Add a Python module and its own parameter JSON under `src/task/step/steps/` or `src/reader/readers/`.
2. Put parameter schema in the adjacent JSON and a literal `definition` with contracts, stable ID, output
   ports and actual resource capabilities. A Step producing a Form must declare
   `definition["output_parameter"] = "output"` or fixed `outputs`.
   Set `category` to its purpose (`quality_control`, `analysis`, `data`,
   `visualization`, or a custom label). Optionally declare an `icon` name, for
   example `"icon": "Funnel"`; otherwise Studio uses the category default icon. See
   [display metadata](operator_protocol.md#operator-categories-and-icons).
3. Run `discover`, then `check` to see missing declarations and duplicate IDs.
4. Add numerical/metadata tests, run `build`, and review the JSON diff.

Every built-in and external class must declare `definition` and reference its parameter JSON.
No schema or calculation defaults are inferred from UI JSON or method source.
An undeclared module fails validation. Scanning cannot infer
the biological meaning of data, implement a streaming kernel, or make an
unbounded calculation fit a memory budget.

Existing package ownership is retained. Unassigned new Steps enter
`biopipe-core`; new Readers enter `biopipe-readers`. An extension can declare
`provider = "biopipe-microbiome"` to create/use a separate installation
unit. New provider metadata starts at version `1.0.0`; review its title/version
in the package manifest before distribution. Moving an already-owned ID into a
different provider is rejected to protect version locks.

`check` validates display field types, parameter schemas, port declarations, output modes, arity,
resource declarations and duplicate identities. Unknown literal parameter reads are errors;
unused/dynamic keys appear in the JSON `warnings` list. It does not prove numerical correctness
or that an optional dependency is installed. `run_stream` and disk-reader hooks
must have real implementations; installation probes validate callable hooks in the worker environment.

## Adding a route without editing Python

Place a `task.yaml` or `task.yml` anywhere under `routes/`. The directory is
recursively discovered. Each file is a normal engine task with `sources` and
`steps`. No route-name list exists in the generator.

An optional neighboring `route.json` supplies stable publishing metadata:

```json
{
  "key": "microbiome",
  "name": "16S Microbiome",
  "base_dir": ".studio/builtin-inputs/microbiome",
  "source_commit": "fa267bc46a30ee9c9483b7442ff119b9aefcf62c"
}
```

Without a sidecar, the relative directory is the identity key and the YAML task
name is the display name. IDs are deterministic hashes of the key. Keep a `key`
or explicit existing `id` when moving a route directory. `enabled: false`
excludes a definition from the generated bundle. Duplicate IDs/display names and
invalid ports, parameters, operators or graph dependencies fail the build.

The generator lays out branches, compiles the DAG, derives input/output contracts
and validates the reusable interface. Route versions increase only when the
generated graph changes. Source hashes use normalized text, so LF/CRLF checkouts
produce the same result. Input paths must be relative; research data is not read
or embedded. The generated files are:

- `biopipe/builtin_packages.json`: all Python providers and descriptors.
- `src/web/builtin_routes.json`: reusable graph snapshots and source provenance.

Deleting a local route definition removes it from the next shipped bundle. It
does not delete users' saved or registered graphs. Startup seeds previously unseen
route IDs, preserves edited snapshots, and respects installation receipts. New
bundled Python packages are discovered during profile upgrade; disabled, removed
and wheel-replaced providers retain their state.

## Inspecting upstream additions

```bash
git fetch origin main
python -m biopipe registry discover --source-ref origin/main
```

This compares local indexed IDs with Step/Reader classes and `tasks/**/task.yaml`
or `routes/**/task.yaml` in a locally fetched Git commit. It reports missing local
sources, changed implementation text and route dependencies. It does not import
upstream code, merge changes, install dependencies or register every operator demo
as a production route. Review/adapt selected source modules, then place published
route definitions under `routes/` and build locally. `--source-ref` is deliberately
limited to `discover`.

## CI and verification

Use `python -m biopipe registry check` as a required CI command after installing
the project. `tests/test_registry_maintenance.py` exercises actual CLI processes
in isolated checkouts: newly added modules/routes, duplicate IDs, missing schemas,
unknown operators, import failures, idempotence, custom roots and profile upgrades.
`tests/test_builtin_routes.py` executes every bundled route with synthetic inputs.
Published desktop packages are updated only by an explicit desktop build/release.
