# BioPipe Studio desktop client

The Windows x64 host uses WinForms and WebView2. It bundles compiled frontend
resources and startup management, while the Python backend and analysis environment
remain independent. Double-click `dist/BioPipe Studio/BioPipe Studio.exe` to launch;
the host starts a local backend, waits for health checks and opens the workspace.
Launching it again activates the existing window for that profile.

## Runtime configuration

The adjacent `biopipe-desktop.json` uses relative defaults:

```json
{"backendRoot":"../..","python":"auto","entryPoint":"scripts/desktop_server.py","frontend":"frontend"}
```

`backendRoot` and `frontend` are relative to the executable. `entryPoint` is relative
to the backend root. Auto-discovery checks project `.venv`/`venv`, active venv/Conda,
PATH Python commands and the Windows Python Launcher, validating Python version and
core dependencies. Invalid environments and Windows Store aliases are skipped.

`python` can also be a path relative to the backend, an absolute path or a PATH
command. `BIOPIPE_PYTHON` and `BIOPIPE_BACKEND_ROOT` override config fields; environment
variables in paths are expanded. An explicitly selected invalid runtime fails with
a diagnostic instead of silently choosing another interpreter.

The target needs a configured backend environment and WebView2 Runtime. The host
includes .NET runtime support; users do not need the .NET SDK. Missing WebView2
produces an actionable message. This local distribution has no installer, signing,
automatic update service or automatic analysis-environment installation.

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
    plugins/                   wheel registry and versioned environments
    agent/                     local discovery and canvas sessions
    assets/                    imported inputs
    jobs/                      graphs, configurations, logs and results
    migrations/<source-id>/    source copies, backups and migration receipts
```

Registries are ordinary JSON files; BioPipe does not modify the Windows registry.
First launch installs GWAS, RNA-seq DE, Proteomics DE and survival templates. Saving
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
and periodically; hot-installed wheels require no backend restart. Built-in Python
source changes still require restart. Sessions expose shared revision-checked UI/
agent edits and undo; separate windows have separate canvas sessions, not a general
multi-user collaboration system. The most recently persisted workspace is restored
on the next fresh launch. Job ownership prevents one window from marking a live
worker in another window as interrupted.

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
python scripts/package_release.py
```

The build restores the WebView2 SDK, copies compiled resources and preserves an
existing desktop config. It does not freeze/copy Python. Rebuild frontend assets
after frontend changes; an old executable directory otherwise shows an old UI.

`package_release.py` creates a clean Windows ZIP under `dist/releases`, including
the Python source, SDK, compiled UI, licenses and a file-checksum manifest. It
excludes user profiles, input datasets, virtual environments and development tools.
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

For agents, use the Agent panel's generated MCP configuration; it uses the actual
runtime and workspace, avoiding PATH/profile mismatches. Moving the application
requires generating the config again. See [agent API](agent_api.md).

References: [WebView2 WinForms](https://learn.microsoft.com/en-us/microsoft-edge/webview2/get-started/winforms)
and [WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution).
