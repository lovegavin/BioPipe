# Moving BioPipe to another computer

Source and default configuration do not depend on a developer drive, username,
Conda installation or terminal working directory. The desktop host targets Windows
x64; the Python engine and browser UI do not require the Windows host.

## Runtime layout

```text
BioPipe/
  biopipe/                     CLI, plugins and agent gateway
  biopipe_sdk/                 public SDK and schemas
  src/                        engine, built-ins and Studio service
  scripts/                    launch/build/verification scripts
  pyproject.toml
  requirements*.txt
  frontend/dist/              built browser resources (optional for desktop-only delivery)
  dist/BioPipe Studio/
    BioPipe Studio.exe
    biopipe-desktop.json
    frontend/                 desktop resources
    ...                       host dependencies
```

Copy the complete desktop distribution, including its DLLs. Python is not frozen
into the executable. Do not copy `.venv`, `node_modules`, `desktop/bin`, `desktop/obj`
or local build caches as a portable runtime. Virtual environments and plugin
generation environments can contain machine-specific interpreter paths.

The target needs Python 3.11+, the Studio dependencies and, on Windows, WebView2
Runtime. A built desktop does not require Node or the .NET SDK. Optional formats
need their packages from `requirements-readers.txt`; analysis extensions use
`requirements-analysis.txt`. For CLI, SDK and plugin development install the
repository package with `python -m pip install -e ".[agent,dev]"` in that environment.

`python: "auto"` discovers a usable project environment, a previously used BioPipe
interpreter, active venv/Conda, PATH Python, Conda environment records and Windows
Python registrations. It does not require an activated terminal. If none works,
select the environment's `python.exe` in the desktop prompt. Successful startup
remembers the current interpreter in `~/.biopipe/runtime.json`; every candidate is
revalidated on the target machine. This personal file is not part of a release.
An explicit `BIOPIPE_PYTHON` or desktop `python` setting overrides discovery and
must be updated after moving; source and packaged defaults never need editing.

```text
python scripts/studio.py
python scripts/run.py tasks/csv_demo
```

You can launch a script by its absolute path from another working directory.
Default profile resolution is independent of cwd. `--workspace` explicitly selects
an isolated workspace; `--data-dir` must remain inside it. `--frontend` selects
compiled frontend resources. `BIOPIPE_STUDIO_HOME` and `--profile-dir` select a
shared profile; relative profile overrides are anchored to the user's home.

## Workflows, plugins and history

Input paths are relative to a graph's `base_dir`, normally the workspace. Uploaded
files and generated demo data use relative paths. YAML exports retain relative
input references; place the export alongside the corresponding base directory and
preserve the data layout. JSON/YAML files do not contain the input data itself.

Carry the complete profile when retaining saved routes and run history, preserving
relative `.studio/jobs`, `.studio/assets` and custom cache locations. Old absolute
paths remain in audit records; history readers map the former workspace to its new
location for previews and downloads. Optional native readers/algorithms still need
target-platform binaries.

Copy plugin wheels and reinstall them on the target. Do not transfer their Python
environments. A saved graph's wheel hash must match; reinstall the original wheel
to satisfy the pin. See [plugin lifecycle](plugins.md). Agent discovery records are
ephemeral: starting Studio publishes a fresh endpoint; no backend port is assumed.

## Verification

```text
python -m pytest -q tests/test_portability.py
python scripts/verify_portability.py
python scripts/verify_runtime_discovery.py
python scripts/audit_portability.py
python scripts/audit_portability.py --package <extracted-desktop-directory>
```

The unit/integration tests cover graph exports, relocated code/data and historical
array/image/cache access. The Windows script starts a relocated executable and
WebView2 from a path containing spaces/non-ASCII characters, checks runtime discovery
and invalid-environment diagnostics, and uses isolated data rather than user routes.

The active-source/package audit rejects literal drive paths and personal home
paths. Packaging runs the same audit before creating a ZIP. Release assemblies
omit source/PDB debug paths. Historical `tasks/*/output` reports and the immutable
v0.4.1 Git snapshot can contain original paths as historical evidence; neither is
used as a current default or included in desktop packages. Verification output,
virtual environments, runtime hints and user profiles are also excluded.
