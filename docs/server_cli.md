# Operon on a Linux server or in a terminal

The desktop is optional. `operon` and the compatibility name `biopipe` use the
same application service, task records, memory planner and workers. YAML is an
authoring format, not a second execution engine. Nothing in this guide requires
a display server, WebView, the Windows application, or an AI model.

## Install once, choose an environment

Use Python 3.11 or newer. Install into a dedicated environment owned by your user,
not the cluster's system Python. For a source release, from its extracted folder:

```sh
python3 -m venv "$HOME/.local/share/operon/runtime-3"
. "$HOME/.local/share/operon/runtime-3/bin/activate"
python -m pip install . ./library
operon --version
```

For wheel releases, install the application wheel and the separately versioned
reference-library wheel. The application is named `biopipe-studio` on the Python
packaging interface for compatibility. The library is `biopipe-builtin-library`;
its version does not have to equal the application version. Add the application
`agent` extra only when this environment will host MCP. No frontend build is needed.

The base application does not include every scientific dependency. Select the
interpreter before starting the service, then prepare dependencies for the route
you intend to run. To change interpreters for an existing workspace, finish or
cancel its active tasks, stop its service, activate the other environment and
start again. A shell using another Python does not silently replace a live service.
`environment status` reports the **service's actual interpreter**, not an assumed
shell interpreter.

Windows Setup deliberately owns its bundled management interpreter and isolated
profile. It does not repoint global Python settings. For independent terminal
projects on Windows, use a source/wheel installation in your chosen environment,
just as on Linux; activate `Scripts/Activate.ps1` instead of `bin/activate`.

## A complete terminal session

Copy `examples/workflows/script_pipeline` to a writable project folder. This
synthetic two-branch example needs only the management runtime. From that folder:

```sh
operon --workspace . workflow lint workflow.yaml
operon --workspace . environment status
operon --workspace . environment check workflow.yaml --require-files
# Only when dependencies are missing, and you want to install them:
operon --workspace . environment prepare workflow.yaml
operon --workspace . run workflow.yaml --progress --brief --request-id example-001
operon --workspace . jobs list
operon --workspace . jobs logs JOB_ID --follow
operon --workspace . artifacts list JOB_ID
operon --workspace . service stop
```

`--workspace .` means the terminal's current directory. Metadata is kept in its
`.studio` directory. Use the same workspace in every command; different workspaces
have independent workflow stores and task histories. Relative input paths in a
YAML route resolve in the selected workspace. Relative parameter, execution and
script sidecar paths resolve beside the YAML document and cannot escape that
project. `workflow lint` and `workflow format` are offline and never start a service.
Formatting does not rewrite parameter values.

Use `operon workflow init my-project` for a generated CSV/PCA starter. It includes
synthetic input data, `workflow.yaml`, `parameters.json`, `execution.json`, a lock
file and optional UI coordinates. Inspect the example before preparing analysis
dependencies. Use `workflow export graph.json --format yaml --output NEW_DIRECTORY`
to export an existing graph with the same strict schema. Existing directories are
not overwritten. See [YAML reference](workflow_yaml_v3.md).

## Validation and explicit preparation

`environment check` and `workflow validate` share the desktop validation service.
They check only the route's operators, Readers and scripts on its selected hosts.
They do not install dependencies. A blocked result is JSON with
`readiness.status = "blocked"` and exit code **1**, so shell automation can stop.
`--require-files` also checks input availability; submission always checks again.

`environment prepare` is an explicit installation request, equivalent to
`workflow prepare-environment`. It uses existing managed dependency targets and
conflict isolation for registered providers. It does not start an analysis job.
A successful probe can be reused during the service session; changes to the
route, pins, input metadata or selected runtime invalidate the relevant readiness.
`run` validates automatically but never silently installs missing packages.

Workflow-local scripts currently check Python requirements and Python/R/C/C++
tool availability. Their unresolved requirements are reported; automatic private
dependency installation for inline scripts is not yet implemented. Install those
requirements in the selected environment explicitly, or promote the script to a
normal provider to use provider preparation and dependency isolation. Do not
interpret a failed preparation as a successful run.

Native tools and named scientific environments must also be available on the
execution host. The existing explicit managed SSH installation can bootstrap
Python and the Hi-C toolchain when no Python is prepared. It remains a separate
installation action, not part of connection, operator registration or validation.
On managed clusters, use the administrator-provided tools/modules or a dedicated
user environment. Operon does not submit Slurm jobs or bypass scheduler policy.

## Batch output, task lifetime and recovery

Normal commands write JSON to stdout; diagnostics and `run --progress` status
changes go to stderr. `--progress` implies `--wait`. `--compact` reduces JSON size.

| Result | Exit code |
| --- | ---: |
| Successful command or completed task | 0 |
| Blocked readiness or failed/cancelled/interrupted waited task | 1 |
| Invalid input or request | 2 |
| Revision conflict | 3 |
| Missing/ambiguous connection or canvas session | 4 |
| Wait timeout (task is not cancelled) | 124 |
| Interrupted terminal wait | 130 |

Without `--wait` or `--progress`, `run` submits and returns a job ID. The detached
service continues after the shell command ends or SSH disconnects. Use
`jobs wait JOB_ID --timeout 60` for a bounded wait, `jobs get JOB_ID --view full`
for full details, and `jobs cancel JOB_ID` to request cancellation. Logs support
bounded byte offsets; failed scripts retain the full native log and surface a
bounded diagnostic tail in the ordinary task log.

The same `--request-id` and identical workflow reuse the original job, including
after service restart. A changed request needs a new ID. This is submission
idempotency, **not** Nextflow-style per-node `-resume`. An interrupted computation
does not gain automatic checkpoints from reusing an ID. See [job lifecycle and
recovery](headless_api.md#retry-and-failure-behavior).

`service status` is read-only and does not start anything. The first application
command starts a loopback-only service; `serve --port 0` runs it in the foreground
for a process manager. `service stop` refuses active tasks. Inspect
`.studio/service.log` for startup failures and `.studio/jobs/JOB_ID/console.log`
for worker diagnostics. Keep the task directory to retain frozen values, pins,
native results and memory reports.

## Memory and concurrent runs

Each project's `execution.json` stores its own execution settings and memory
budget. Direct Linux runs use Linux memory availability and the shared host
admission ledger; SSH stages use the server's ledger and memory planner. Budgets,
planned spill, emergency spill and streaming retain their existing meaning.
Concurrent submissions queue when host capacity is unavailable. A ready validation
is not a capacity reservation. A full-memory operator does not become streaming
because it runs on a server. See [execution and retained task state](headless_api.md).

## Let desktops reuse this server

After verifying a Linux installation, register it once with the installed Python:

```sh
python -m biopipe.remote.installation register \
  --base "$HOME/.local/share/operon/server" \
  --workspace "$HOME/operon-projects/shared"
```

The command writes `server.json` pointing to this interpreter and application.
In Studio's server settings select SSH and an existing installation, set the
server base to that directory, and connect. The private workspace and files stay
on the server. Routine reconnects read the manifest and do not upload the program
or install dependencies. Use separate workspace directories for unrelated users
or projects; the SSH account's filesystem permissions remain authoritative.

Compared with 2.6, 3.0 adds public YAML, script snapshots, selected-host readiness
and explicit route environment preparation. The SSH framing and operator v3/v3.5
compatibility remain. New clients require the `workflow_readiness` handshake
capability and reject older servers before submitting. Upgrade an old installation
explicitly after active work finishes; a new client never silently overwrites it.

## Reproduce the terminal acceptance

From a source release, run with the intended interpreter:

```sh
python scripts/verify_server_cli.py --work-dir /path/to/new-acceptance-directory
# Optional: explicitly prepare and run the CSV/PCA starter as well.
python scripts/verify_server_cli.py --work-dir /path/to/another-new-directory --prepare-analysis
```

It runs actual CLI processes, a two-branch YAML workflow, frozen parameters,
readiness failure, logs/artifacts, service restart, idempotent reuse and a failing
script. It leaves a JSON report and command logs. It uses synthetic data only.
This suite does not imply every optional scientific operator, native tool or
cluster scheduler has been validated.
