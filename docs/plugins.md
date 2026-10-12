# Plugin installation and version lifecycle

Studio, CLI and MCP locate the same data directory through `src/web/profile.py`.
The default is `~/.biopipe/studio/workspace/.studio`. A user can select a profile
with `BIOPIPE_STUDIO_HOME` or `--profile-dir`, or use an explicit `--workspace`.

```text
<data directory>/
  operators.json
  plugins/
    registry.json                 active generation and descriptors
    packages/<sha256>/<file>.whl   immutable cached packages
    environments/<generation>/
      lock.json                   package identities and descriptors
      constraints.txt             inherited runtime dependency versions
      probe.json                  installation-time descriptor output
      Scripts/python.exe          Windows worker (bin/python on POSIX)
  jobs/<job>/plugins.lock.json     exact worker generation selected for a job
```

## Installation transaction

1. Accept a local wheel, validate its metadata and cache it by SHA-256.
2. Take the cross-process installation lock. Build a new environment containing
   the complete requested plugin set; normal catalog reads continue during this work.
3. Inherit the application's current runtime dependencies and constrain their
   versions. Resolve additional dependencies inside the new environment. A conflict
   with the active runtime fails rather than upgrading the application's environment.
4. Probe entry points in a separate process. Check descriptors, namespace uniqueness,
   contracts and any embedded manifest. The GUI process never imports plugin code.
5. Publish `lock.json`, then atomically replace `registry.json`. Studio detects the
   new generation and updates `operators.json`; open windows refresh their library.

A failed installation leaves the old active registry intact. Diagnostic/staging
directories may remain for investigation. There is no automatic environment garbage
collection in v1 because old jobs/routes can still reference them.

## Upgrade, removal and saved routes

An inserted/saved graph is pinned when prepared, saved or launched. A pin contains
the package name, package version and wheel digest. Nested route snapshots retain
their pins. New unpinned insertions use the current generation. Running jobs record
and keep their original Python environment even if another installation finishes.

`biopipe plugin remove <distribution-name>` publishes a generation without that
package. It does not delete its wheels or historical environments. Saved pinned
graphs can still run against a matching generation. Route saving and registration
also validate against the graph's pinned catalog, including after removal.

One execution uses one compatible plugin environment. Combining snapshots pinned
to incompatible plugin sets fails with an explicit message; v1 does not build a
cross-version environment automatically or run different nodes in different Python
interpreters. To deliberately upgrade a saved graph, export it, clear the relevant
`plugin_lock` entries (also inside nested snapshots), validate, and save as a new
version. Existing route instances are never silently rewritten.

Use Studio/agent graph execution for plugin pipelines: it creates the required
`plugins.lock.json` and launches the selected interpreter. A plain YAML export does
not embed the plugin environment; `scripts/run.py` loads a lock only when one is
present alongside the task. Original built-in-only YAML tasks remain unchanged.

## Moving to another computer

Transfer source/wheels, graph JSON and required input data. Install BioPipe in a
working environment on the target computer, then install the original wheels there.
Matching wheel digests allow the saved pins to resolve. Do not copy Python virtual
environments between computers: interpreter paths and native binaries are local.
The cached lock stores relative environment paths, but the generated Python
environment itself is not portable. Reinstall from wheels after moving the runtime.
Runtime logs may contain resolved absolute paths for auditing; application defaults
do not contain developer-specific paths.

## Trust and capabilities

Python plugins are executable code with the current user's permissions. Dependency
isolation is not an OS sandbox. Installation requires an explicit CLI command or an
MCP connection started with `--allow-plugins`. BioPipe does not download arbitrary
code based on graph labels. MCP defaults permit context and graph editing, with job
execution and plugin installation requiring separate capabilities.

See [quickstart](sdk_quickstart.md) and [agent interface](agent_api.md).
