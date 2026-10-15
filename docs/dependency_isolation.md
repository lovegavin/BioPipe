# Selective dependency isolation

BioPipe uses **one Python executable**. Compatible operators run in the pipeline
worker with shared dependencies. A declared direct or transitive version conflict
selects a private dependency directory and a fresh subprocess for that operator.
It does not create another Python installation, rewrite imports, or rename packages.

## Author declarations

Declare distribution requirements on the Step or Reader, for example:

```python
class OlderAnalysis(Step):
    dependencies = ["some-library>=1,<2"]
    dependency_imports = ["some_library"]
    # Normal name, schema, contracts, run and export definitions follow.
```

Another operator can declare `some-library>=2,<3`. If version 2 is already shared,
only the version-1 operator is isolated. Keep requirements literal so source
scanning can prepare dependencies before importing a module. A direct SDK subclass
in a single-file drop-in gets its own dependency declaration. Module-wide
`BIOPIPE_PLUGIN.dependencies` and wheel `project.dependencies` apply to **every**
entry in that module/package. Do not put contradictory per-operator requirements
in the common package requirements. SDK-generated manifests preserve per-entry
requirements; generated provider modules load entries lazily.

Ordinary Python imports keep their normal meaning inside each process. Modules
that eagerly import sibling implementations also require those siblings' imports.
Use separate modules or lazy imports when siblings need conflicting dependencies.
Dynamic declarations cannot always be discovered before import; prefer literal
class declarations and an SDK-generated wheel manifest.

## Installation and readiness

1. Freeze source/wheel bytes and validate package identity.
2. Ask pip to resolve against the current shared versions, without modifying them.
3. Add compatible missing dependencies to an immutable target directory. If
   resolution reports a version conflict, resolve the operator's full declared
   dependency closure into a private target directory instead.
4. Probe real entry classes under their selected paths and validate the protocol.
5. Publish the registry generation atomically. Existing jobs keep their frozen lock.

Network errors, unsupported Python versions and missing native wheels are not
classified as dependency conflicts. Failed installation keeps the active registry.
When an environment creator omits pip, the installer can run CPython's bundled
ensurepip wheel directly. This adds no packages to the base environment and
creates no extra interpreter. A Python distribution with neither pip nor that
bundled wheel reports an explicit installer requirement.
Unchanged optional Reader declarations can remain registered but not ready;
their readiness/repair is independent of unrelated library entries.

Startup and library changes check enabled entries. A successful check remains
passed for the session. Retries visit only non-passed entries. Changing an
implementation, declaration or execution target invalidates its own status.
Repairs publish only after the selected target passes; one failed repair does not
discard other successful repairs. The library manager shows **Independent
dependency process** for isolated entries (localized in the UI).

Targets are under the resolved data directory's `plugins/targets/`. Provider code
is under `plugins/environments/<generation>/code/`; despite the historical folder
name, these new generations contain no Python executable or virtual environment.
Registry paths to these folders are relative. Old virtual-environment generations
remain readable for existing saved routes. Reinstall wheels when changing OS,
architecture or Python ABI; private native dependencies are not portable across
those boundaries.

## Execution and data exchange

The host launches its own `sys.executable` with isolated startup flags, installs
the selected search paths before loading third-party modules, then loads the
selected Step or Reader. The UI process never imports extension code. Compatible
operators keep the existing in-process execution path.

The local exchange protocol uses tagged JSON and NPY files, not pickled
dependency-owned objects. Forms preserve `dims`, `labels`, `info`, `axis_info`,
NumPy metadata arrays, non-finite floats and BioPipe LabelEncoder mappings.
Lists, tuples, sets, dictionaries and paths retain their types. Arbitrary custom
Python objects and object-dtype arrays fail with an explicit type error; convert
such metadata to supported values before crossing the boundary.

- Full mode supplies copy-on-write mapped input files. The custom
  `estimate_memory` hook still runs, in the selected dependency process. Admission
  adds input residency and transport buffers to its estimate. Input mutation in
  the child cannot modify the parent's input cache.
- `flat-reduction-v1` sends one bounded numeric block at a time with an
  acknowledgement before reuse. It never concatenates the stream for transport.
- `dense-writer-v1` Readers still probe metadata and write bounded blocks through
  the parent's DenseDiskWriter. Dense preparation, emergency block spilling and
  subsequent operator planning remain separate stages.
- Outputs are read after the child exits, avoiding overlap with the child's
  retained output arrays. The normal parent output contract and cache registration
  still apply. Report exports and artifact paths keep their existing interface.

The child gets the declared input Forms and normal Context methods for outputs,
logs and artifacts. Undeclared access to unrelated Context Forms and direct use of
the parent's internal memory store are not cross-process APIs. Declare required
inputs and implement the documented resource hooks instead.

## Resource accounting and diagnostics

The pipeline retains the original available-memory snapshot; isolation does not
scan available RAM again. Stream reservations include transport blocks. Full-mode
reservations include the child's possible input residency. RSS sampling includes
the worker's descendants, and the emergency spiller can release unpinned cache
when the aggregate process limit is approached. A process-limit admission failure
terminates the isolated call. This remains estimated admission and sampled
feedback, not an operating-system hard memory cap.

Exchange files and in-progress dense files share the run disk quota with cached
artifacts. Temporary exchange directories are removed after success or failure.
Run events include `isolated_started`, `isolated_finished` or `isolated_failed`,
operator ID, operation and process ID. Child stdout/stderr goes to the existing
pipeline console; structured `ctx.log` events and tracebacks remain in normal run
logs. Framed control messages keep direct native-library stdout separate from
the exchange protocol. Cancelling the desktop job stops its process tree,
including isolated calls.

Dependency repair does not solve incompatible operating-system libraries, GPU
drivers, Python language versions, or an internally contradictory requirement set
inside one operator. Such failures remain visible with the resolver/import error.

Implementation references: [pip resolution reports](https://pip.pypa.io/en/stable/cli/pip_install/#obtaining-information-about-what-was-installed)
and [Python isolated startup](https://docs.python.org/3/using/cmdline.html#cmdoption-I).
