# BioPipe Studio desktop client

The Windows x64 host uses WinForms and WebView2. It bundles compiled frontend
resources and startup management. Full release archives also contain a relocatable
Python runtime and the built-in CPU dependencies. Double-click `BioPipe Studio.exe` to launch;
the host starts a local backend, waits for health checks and opens the workspace.
Launching it again activates the existing window for that profile.

## Runtime configuration

The adjacent `biopipe-desktop.json` uses relative defaults:

```json
{"backendRoot":"../..","python":"auto","entryPoint":"scripts/desktop_server.py","frontend":"frontend"}
```

`backendRoot` and `frontend` are relative to the executable. `entryPoint` is relative
to the backend root. Auto-discovery checks the remembered interpreter, project
`.venv`/`venv`, active venv/Conda, PATH Python commands, the Windows Python Launcher,
Conda's `~/.conda/environments.txt` and Windows Python registrations (PEP 514).
Full packages set `bundledRuntime: true` and exclusively use their adjacent
`runtime/python/python.exe`; a remembered interpreter or `BIOPIPE_PYTHON` cannot
silently replace it. `--select-runtime` is an explicit maintenance override for
one launch. See
[bundled runtime](installation.md#bundled-windows-runtime) for the full build recipe
and automatic WebView2 setup. Lite/source builds and 0.3.4 packages use environment discovery.

Each candidate is checked for Python 3.11+ and core dependencies. Invalid
environments and Windows Store aliases are skipped; no whole-disk scan is used.

Successful development/desktop startup remembers its interpreter in
`~/.biopipe/runtime.json`. This machine-local bootstrap hint is shared across
release folders and is independent of canvas profiles, because the host needs
Python before it can resolve the full profile. It is never bundled into releases.
`BIOPIPE_RUNTIME_CONFIG` can select a separate file (relative paths are relative
to the user home). Missing, stale or corrupt hints do not prevent other discovery.

If automatic discovery fails, the desktop offers a file picker for an existing
environment's `python.exe`. Validation runs before it is remembered. Use
`BioPipe Studio.exe --select-runtime` to choose again. Explicit config/environment
overrides still take priority over remembered hints on subsequent launches.

For lite/source builds, `python` can also be a path relative to the backend, an absolute path or a PATH
command. `BIOPIPE_PYTHON` and `BIOPIPE_BACKEND_ROOT` override config fields; environment
variables in paths are expanded. An explicitly selected invalid runtime fails with
a diagnostic instead of silently choosing another interpreter.

The full package includes Python and .NET runtime support; users need neither SDK.
Missing WebView2 is prepared with the included signature-verified Microsoft
bootstrapper, using internet access. The host starts Python in isolated mode and
removes inherited `PYTHONHOME`/`PYTHONPATH` from the backend environment. New operator
dependencies are maintained in the Studio profile; the bundled runtime is not
modified. This distribution has no automatic application-update service.

## Shared profile

The exe, `scripts/studio.py`, CLI, MCP and default `create_app()` share
`~/.biopipe/studio`. Only `src/web/profile.py` defines this policy; the host asks
Python to resolve it. The default does not use AppData or depend on cwd.

```text
~/.biopipe/studio/
  browser/                     WebView2 browser state
  logs/desktop-YYYYMMDD.log     startup/backend/shutdown logs
  port.txt                     last preferred loopback port
  workspace/.studio/
    operators.json             generated catalog
    draft.json                 legacy single-page draft
    workflows/
      workspace.json           open/closed pages and view preferences
      route_<id>.json          saved routes and interfaces
      registry.json            explicitly registered route snapshots
      library_state.json       disabled/hidden library items
      builtins_installed.json  bundled-route installation receipt
    plugins/                   registry, frozen provider code and dependency targets
    agent/                     local discovery and canvas sessions
    assets/                    imported inputs
    jobs/                      graphs, configurations, logs and results
    migrations/<source-id>/    source copies, backups and migration receipts
```

BioPipe registries are ordinary JSON files; discovery reads, but never modifies,
the Windows registry.
First launch installs the shipped route templates, including GWAS, RNA-seq DE, proteomics DE, survival, 16S microbiome, single-cell, annotation, interval, GO, sequence, multi-omics and ML templates. Saving
a graph does not register it: select saved routes with the library plus button.

Default startup imports known legacy repository/AppData/package-sandbox directories
once per source. It preserves source files and receipts, merges identical snapshots,
separates ID collisions, imports referenced workspace-local inputs and keeps old
large caches/run history in place. Missing/out-of-workspace inputs produce receipt
warnings. Corrupt registry files fail visibly rather than being overwritten as empty.

Both entry points accept `--profile-dir` or `BIOPIPE_STUDIO_HOME`; explicit argument
wins over environment, then default. Relative profile paths are home-relative.
The exe's old `--data-dir` is an alias for `--profile-dir`. Python `--workspace`
selects an isolated workspace with `.studio` by default; its `--data-dir` is a
workspace-relative legacy override. Explicit profiles/workspaces disable default
legacy import. `BIOPIPE_STUDIO_DATA` is supported only with explicit workspace mode.

Cross-process locks and atomic files protect registries. Libraries refresh on focus
and periodically; hot-installed wheels require no backend restart. Use **Refresh
operator library** after editing Step or Reader sources in the directories shown
by Library Management. The scanner freezes a new generation for subsequent jobs;
already running jobs keep their existing generation. See [hot refresh](plugins.md#drop-refresh-use).
Sessions expose shared revision-checked UI/
agent edits and undo; separate windows have separate canvas sessions, not a general
multi-user collaboration system. The most recently persisted workspace is restored
on the next fresh launch. Job ownership prevents one window from marking a live
worker in another window as interrupted.

## Run diagnostics

Open **Run logs** for structured engine events, operator messages and the actual
process output. The view shows the last 64 KiB of process output; **Full process
log** downloads the complete file. This is a display bound, not a stored-log limit.

Each job directory in the active profile contains:

- `job.json`: status, recorded error, timestamps, worker exit code and whether logs
  have finished flushing. Windows exit codes are also printed in hexadecimal.
- `console.log`: launcher header, Python stdout/stderr, tracebacks and exit record.
- `launcher.events.jsonl`: startup/exit events written by the backend independently
  of the analysis worker. A failed process launch returns a failed job with logs.
- `output/runs/<run-id>/events.jsonl`: engine and operator events, also generated
  when memory management is disabled.
- `output/run_summary.json`: final summary, including failures during engine import,
  plugin loading or task initialization. A native crash or forced process exit may
  prevent this summary; the launcher still records the exit code. Python fault
  handling is enabled for native failures that Python can report.

The UI waits for final log flushing before closing its event connection, including
after cancellation. Reopening a completed run reads its stored logs. Historical
empty/missing console files show the recorded job error with an explicit notice
that no worker output was captured; the original files are not rewritten and an
unrecorded historical exit code cannot be reconstructed. The profile is resolved
on the user's computer; none of these paths refer to the developer's computer.

## Startup and shutdown

1. One desktop instance owns a profile; repeated launches focus its window.
2. Bind only `127.0.0.1`, prefer the previous port and fall back when occupied. Keep
   the allocated socket until service startup to avoid a port allocation race.
3. Start backend work only after the host attaches its process tree to a Windows
   Job Object. The host manages only processes it created.
4. The frontend reports ready after loading catalog/drafts. Closing flushes the
   workspace, then requests graceful backend shutdown through stdin. Active jobs
   prompt the user before stopping and exiting.
5. Closed stdin shuts down the backend. A terminated host's Job Object reaps its
   workers. Incomplete records are marked interrupted on the next startup.
6. WebView navigation stays at the current local backend; external links open in
   the system browser. The UI uses its local session token. CLI/MCP obtain separate
   scoped tokens; graph editing does not trigger execution.

## Build and verify

The build machine needs .NET 8 SDK, Node and the Python environment:

```powershell
./scripts/build_desktop.ps1
./scripts/build_desktop.ps1 -SkipFrontend
python scripts/package_release.py --runtime .local/runtime/python
python scripts/package_release.py --lite
```

The build restores the WebView2 SDK, copies compiled resources and preserves an
existing desktop config. It does not freeze/copy Python. Rebuild frontend assets
after frontend changes; an old executable directory otherwise shows an old UI.

`package_release.py` creates a clean Windows ZIP under `dist/releases`, including
the Python source, SDK, compiled UI, licenses and a file-checksum manifest. It
excludes user profiles, input datasets, virtual environments and development tools.
The default archive includes the environment prepared by `build_runtime.py`;
the `-Lite.zip` archive instead discovers an existing Python environment.
Run it from a committed checkout after the frontend and desktop builds so that its
source commit identifies the released code. The output directory must be new.

`--smoke-test --data-dir <temporary-profile>` starts the real backend and WebView2,
waits for React, flushes drafts and exits (0 on success). `--check-runtime` resolves
the interpreter without opening a window. `--check-profile` prints the same paths
as `python scripts/studio.py --resolve-profile`. `/api/bootstrap.storage` shows the
live profile, workspace and registry when diagnosing a running instance.

`python scripts/verify_desktop.py` checks loading, duplicate launch, occupied-port
fallback, process-tree cleanup and draft/task recovery in isolated test profiles.
`python scripts/verify_portability.py` additionally checks relocated paths, alternate
working directories and runtime discovery. Evidence is saved under `.verification`.
`python scripts/verify_runtime_discovery.py` covers a remembered environment with
empty PATH and no activated shell, stale records, explicit overrides, Conda records
and a complete real WebView2 startup/shutdown. Test runtime hints are isolated from
the user's own hint. `--check-runtime` remains read-only and never opens a picker.

For agents, use the Agent panel's generated MCP configuration; it uses the actual
runtime and workspace, avoiding PATH/profile mismatches. Moving the application
requires generating the config again. See [agent API](agent_api.md).

References: [WebView2 WinForms](https://learn.microsoft.com/en-us/microsoft-edge/webview2/get-started/winforms)
and [WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution).
