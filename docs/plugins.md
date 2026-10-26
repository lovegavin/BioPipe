# Plugin installation and version lifecycle

All built-in operators and Readers ship as six preinstalled packages.
These include the eight microbiome operators; see [16S analysis](microbiome.md).
Use whole-library refresh below for runtime additions, or
[registry maintenance](registry_maintenance.md) to maintain the repository's shipped indexes.
The same registry manages bundled and wheel providers. See
[unified package/resource protocol](package_protocol.md) for package ownership,
hot replacement, enable/disable/restore, and public stream/disk hooks.

Studio, CLI and MCP locate the same data directory through `src/web/profile.py`.
The default is `~/.biopipe/studio/workspace/.studio`. A user can select a profile
with `BIOPIPE_STUDIO_HOME` or `--profile-dir`, or use an explicit `--workspace`.

```text
<data directory>/
  operators.json
  plugins/
    inbox/                        .py files, wheels, or plugin project folders
    registry.json                 active generation and descriptors
    snapshots/<generation>.json   non-installation lifecycle snapshots
    packages/<sha256>/<file>.whl   immutable cached packages
    environments/<generation>/
      lock.json                   package identities and descriptors
      code/                       immutable provider code (no interpreter)
    targets/<id>/                 shared or private dependency files
  jobs/<job>/plugins.lock.json     exact worker generation selected for a job
```

## Drop, refresh, use

The **whole operator library** supports hot refresh, including preinstalled
operators and Readers. Open **算子库管理** (operator library management), then
**算子目录** or **Reader 目录** to open the existing source directories:

- Operators: `<application root>/src/task/step/steps/*.py`
- Readers: `<application root>/src/reader/readers/*.py`

Add or edit a normal, protocol-compliant `Step`/`Operator` or `Reader` file, then
click **刷新算子库** in the dialog or the refresh icon beside the library heading.
The class declarations provide the ID, parameters, contracts, category, icon and
memory capabilities. No extra plugin project, hand-written registry or manual
packaging step is required. Existing built-in authoring style and IDs are supported;
`builtin_package` selects a provider when needed. Existing ownership is preserved.

Authors may set `icon = "icons/my-operator.png"` (also JPEG, WebP, GIF or static SVG)
and place that image relative to the operator's Python file. Refresh freezes the
image with the descriptor; editing only the image is enough to trigger an update.
No absolute paths or external image server are needed. Omit `icon` for an automatic
category default, or keep an existing bundled icon name. See the
[image declaration reference](operator_protocol.md#operator-categories-and-icons).

The scanner snapshots both source trees and their declared image resources, imports them
in a separate process, validates the public protocol, and prepares immutable
provider code internally. Only a completely successful scan/installation replaces
the active profile registry. The first refresh freezes the managed source library;
later refreshes skip unchanged source content. Source updates retain disabled
providers and do not resurrect removed providers or override independently installed
provider wheels. This is the same operator library and execution engine, not a
parallel extension-only system. Stream operators and disk Readers retain their hooks.

The CLI equivalent is `biopipe plugin refresh`; `biopipe plugin list` reports
`source_directories` and the optional `inbox`. Paths are resolved from the running
application and selected profile, never from a fixed drive or developer account.
Desktop and development launches sharing a profile read the same active registry.
Refresh scans the source directories displayed by that instance. A read-only
application installation can instead use the writable **附加目录** (additional folder).

Source refresh updates the **active profile**, not the checked-in JSON manifests.
Maintainers still run `biopipe registry build` before committing/publishing source
changes. Declare algorithm dependencies on the Reader/Step class as literal
`dependencies = ["package>=version"]` and, optionally,
`dependency_imports = ["module_name"]`. Refresh reads those declarations before
importing source and prepares missing compatible dependencies automatically.
Undeclared imports cannot be installed reliably; scan failures leave the active
library intact. Wheel projects must also use standard `project.dependencies`.
See the [dependency contract](operator_protocol.md#dependency-declarations).

Startup and completed library changes check dependency readiness for enabled
entries. Passed results remain cached for the session, while **Repair dependencies**
retries failures. The manager displays status and error details and writes
`logs/dependencies.jsonl` under the resolved data directory. Compatible entries
share dependencies; conflicting entries use private dependency directories and
subprocesses with the same Python executable.
The GUI remains responsive during preparation, and closing Studio cancels its
dependency subprocesses. See [installation](installation.md#dependency-state).

## Optional additional folder and package imports

The additional folder is a convenience for self-contained extensions and shared
packages. It is not required when editing the normal operator/Reader directories.

Supported inputs, placed directly inside `inbox/`:

- **One `.py` file:** define concrete SDK `Operator`/`Step` and/or `Reader` classes
  in the file, with unique namespaced IDs, parameter schemas and contracts. All
  eligible classes defined in that module are discovered. Imported and abstract
  classes are excluded. No manual JSON registry or wheel build is needed.
- **One `.whl` file:** the existing unified package protocol and validation apply.
- **One project folder:** include `pyproject.toml` with the usual
  `biopipe.operators` / `biopipe.readers` entry points. BioPipe snapshots the folder
  and runs `pip wheel --no-deps` with build isolation, then installs the result.
  Build requirements and additional runtime dependencies may need network access.

For a single file, an optional **literal** module-level dictionary supplies the
package identity and additional dependencies before the module is imported:

```python
BIOPIPE_PLUGIN = {
    "name": "my-lab-scale",       # Stable distribution name, independent of the file path
    "version": "0.1.0",
    "dependencies": ["numpy>=1.26"],
}
```

Without this dictionary, the distribution name is derived from the filename and
the version defaults to `0.1.0`. The operator's `name` remains its own declared ID.
Keep the filename stable, or declare a stable package name before sharing. A source
change is detected by content hash even if its version number is unchanged.
Use stable SDK imports; files relying on relative imports, helper modules or data
files should be distributed as a complete project folder/wheel instead. Declared
image icons are an exception: literal `icon` paths are copied into the generated
package. Put shared images in `icons/` or `assets/`; these folders are skipped as
standalone projects unless they contain `pyproject.toml`.
See [the single-file example](../examples/dropins/scale.py); copy its `icons/` folder
too, or remove the `icon` declaration to use the category default.

Refresh takes one snapshot of each input, skips unchanged content, prepares all
changed packages in one new environment, and publishes the registry **only after
the entire batch validates**. Missing dependencies, syntax errors, invalid contracts,
duplicate IDs or conflicting packages leave the previous active generation intact.
Errors name the source input/package. Reader file types, schemas, categories,
optional icons and stream/disk capabilities become available through the same live
catalog. Neither the backend nor the desktop needs to restart.

The scan is explicit, not a filesystem watcher. Normal library polling only reads
metadata. It does not repeatedly execute plugin code. Build/cache directories such
as `.git`, `.venv`, `build`, `dist` and `__pycache__` are ignored; linked files and
directories are rejected. The user's original sources are never built in place.
Keep one input per distribution in the folder. Removing a file does not uninstall
its package: use the package manager. Refresh preserves disabled packages and does
not reinstall an unchanged file after an explicit package removal. To reinstall it,
use **Install / Update** with its wheel, or change/rebuild its source.

All inputs still become ordinary cached wheels and immutable environment snapshots.
Single-file wrappers use the `biopipe.modules` entry-point group for isolated
module discovery; their generated wheels require a BioPipe version supporting this
group. They do not introduce a second execution or memory-management protocol.

Refresh never edits the scanned source files or fetches code from GitHub.

## Installation transaction

1. Accept a local wheel, validate its metadata and cache it by SHA-256.
2. Take the cross-process installation lock. Stage the provider code in a new
   immutable generation; catalog reads continue during this work.
3. Preserve shared versions. Add compatible dependencies to shared target
   directories; resolve conflicting entries into private dependency directories.
   Every call still uses the same Python executable. No new venv is created.
4. Probe entry points in a separate process. Check descriptors, namespace uniqueness,
   contracts and any embedded manifest. The GUI process never imports plugin code.
5. Publish `lock.json`, then atomically replace `registry.json`. Studio detects the
   new generation and updates `operators.json`; open windows refresh their library.

A failed installation leaves the old active registry intact. Diagnostic/staging
directories may remain for investigation. There is no automatic environment garbage
collection because old jobs/routes can still reference them.

## Upgrade, removal and saved routes

An inserted/saved graph is pinned when prepared, saved or launched. A pin contains
the package name, package version and implementation digest (wheel or bundled
content fingerprint). Nested route snapshots retain
their pins. New unpinned insertions use the current generation. Running jobs record
and keep their original dependency paths even if another installation finishes.

Built-in source checkouts need one distinction: older bundled registry snapshots
stored fingerprints, not copies of the Python source. After a source update,
Studio recognizes those historical **bundled** pins and resolves new runs against
the current bundled implementation. It validates the graph against the selected
contracts and records `bundled_updates` (old/new identities) in the new job lock,
job metadata and run events. The same resolution applies to nested route graphs.
Historical jobs, saved JSON files and their logs are not rewritten. Save the
prepared graph as a new version to persist the updated pins.

This fallback requires a matching bundled entry in the profile's registry history.
Unknown pins and installed wheel pins remain strict; real plugin generations keep
their original code and dependency targets. For exact historical built-in replay,
retain the original BioPipe source/release or distribute the provider as an
immutable wheel. A metadata-only snapshot cannot reconstruct deleted source.

The manifest and known source-file metadata invalidate the lightweight fingerprint
cache when files change; unchanged files do not trigger imports or registry scans.
If source is edited after a job has already been created, the worker still checks
the frozen fingerprint and refuses to execute different bytes under that lock.
Create a new run once the source update is complete.

`python scripts/diagnose_pins.py --profile-dir <profile>` reports old pins without
changing them. The obsolete `repin_all.py` alias has been removed.
Historical locks are never rewritten by diagnostics or profile migration. The normal profile environment override is supported as well.

`biopipe plugin remove <distribution-name>` publishes a generation without that
package. It does not delete its wheels or historical environments. Saved pinned
graphs can still run against a matching generation. Route saving and registration
also validate against the graph's pinned catalog, including after removal.

A pipeline may combine different dependency versions through isolated processes.
Combining conflicting pins for the same operator identity still fails explicitly.
See [selective dependency isolation](dependency_isolation.md).
To deliberately upgrade a saved graph, export it, clear the relevant
`plugin_lock` entries (also inside nested snapshots), validate, and save as a new
version. Existing route instances are never silently rewritten.

Use Studio/agent graph execution for plugin pipelines: it creates the required
`plugins.lock.json` and launches the selected interpreter. A plain YAML export does
not embed the plugin environment; `scripts/run.py` loads a lock only when one is
present alongside the task. Original built-in-only YAML tasks remain unchanged.

## Moving to another computer

Transfer source/wheels, graph JSON and required input data. Install BioPipe in a
working environment on the target computer, then install the original wheels there.
Matching wheel digests allow saved pins to resolve. New generations use relative
dependency-directory paths; old venv generations remain readable. Reinstall from
wheels after changing Python ABI, architecture or operating system because native
dependency files are platform-specific.
Runtime logs may contain resolved absolute paths for auditing; application defaults
do not contain developer-specific paths.

## Trust and capabilities

Python plugins are executable code with the current user's permissions. Dependency
isolation is not an OS sandbox. Installation requires an explicit CLI command or an
MCP connection started with `--allow-plugins`. BioPipe does not download arbitrary
code based on graph labels. MCP defaults permit context and graph editing, with job
execution and plugin installation requiring separate capabilities.

See [quickstart](sdk_quickstart.md) and [agent interface](agent_api.md).

## Studio plugin manager

Open **算子库管理** (operator library management) to install a local `.whl`, inspect
installed packages and their Reader/operator entries, or remove a package from the
active generation. Wheels execute Python code during installation/probing: install
only packages you trust. Installation runs outside the HTTP event loop and publishes
the registry only after validation. The dialog reports running, complete or failed
status, then refreshes the library. Existing version-pinned canvases retain their
archived environments after removal. The CLI remains supported.

The local session-token-protected API provides `GET /api/plugins`,
`POST /api/plugins/install?filename=<wheel>` (streamed raw bytes),
`POST /api/plugins/remove` (`{"name":"distribution-name"}`),
`POST /api/plugins/manage` (`{"name":"distribution-name","action":"enable|disable|restore"}`), and
`GET /api/plugins/operations/<id>`. The optional upload cap also applies to wheels.
These routes do not grant install permission to an external agent token.

`POST /api/plugins/refresh` starts the asynchronous library refresh transaction and
returns an operation ID. The completed operation's `result` contains `updated`,
`unchanged`, `generation`, `operators`, `readers` and `directory`.
`GET /api/plugins` includes `inbox` and `source_directories`;
`POST /api/plugins/open-folder` accepts `{"kind":"operator|reader|extra"}` and opens
only the corresponding resolved folder in the local file manager. These POST endpoints require
the Studio session token. A concurrent UI plugin operation receives HTTP 409;
CLI and UI installations also share the cross-process installation lock.
