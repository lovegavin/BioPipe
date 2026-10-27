# Windows editing and SSH execution

BioPipe Studio v0.7.1 can prepare a Linux server and run a workflow over SSH. Choose an execution
target in the top toolbar, select server files in the input inspector, then use
the existing **Check**, **Run**, **Stop**, results and log controls. This feature
is included in both the full and Lite Windows desktop archives.
The Windows/Linux execution results are recorded in [REMOTE_VALIDATION.md](REMOTE_VALIDATION.md),
and automatic deployment results in [AUTO_DEPLOY_VALIDATION.md](AUTO_DEPLOY_VALIDATION.md).
For automatic input uploads, mixed local/SSH
stages and concurrent task manager, see [execution environments](EXECUTION_ENVIRONMENTS.md).

## Prepare the server

New connections default to **Automatic deployment: BioPipe + Hi-C**. Supply the
SSH endpoint and authentication, verify its host fingerprint, and connect. No
preinstalled Python or Conda is required. The account needs Linux x86_64, Bash,
tar, base64, sha256sum, flock, curl or wget, outbound HTTPS and writable disk space.
The installer downloads a checksum-pinned static micromamba executable from its
official conda-forge archive, then creates a private Python 3.11 environment with
BWA, samtools and the compilers needed for native Python extensions. One pip solve
installs all bundled provider requirements together with pairtools, cooler and
cooltools. This avoids replacing NumPy underneath conda-built scientific extensions.
It checks
the installed packages, import probes and tool executables before connecting.

The default installation directory is `$HOME/.local/share/biopipe`, resolved on
the server. It can be changed in the connection panel. The default run directory
is `workspace/` below that location. No sudo, system Python modifications, shell
startup edits, or global Conda activation are used. Existing connection records
remain in **Use existing environment** mode until you choose automatic deployment.

Only application code, catalogs and parameter schemas are uploaded; local input
datasets, profiles and credentials are excluded. The source archive is checked
by SHA-256 before extraction. Code and environment paths are keyed by the source
digest, so updating the desktop does not overwrite an older execution environment.
Repeated connections reuse the same installation and check its requirements,
including missing or incompatible transitive dependencies reported by `pip check`.
Dependency downloads and installation occur only when required. An installation
lock serializes changes from multiple clients. The panel shows progress and errors;
the server retains `managed-v1/setup-<digest>.log` for diagnostics. Failed attempts
do not publish a readiness receipt; reconnect to retry. Cancellation stops waiting
and closes SSH; allow any outstanding installer to release its lock before retrying.

### Use an existing environment

Use a Linux account that can read the input data and write its run directory.
Place the same BioPipe source revision on the server, including `scripts/run.py`,
the generated bundled catalog and the independent `*.parameters.json` files.
Prepare Python 3.11+ and the dependencies of the operators you will use. For Hi-C,
follow [the Linux environment instructions](HIC.md#linux-tool-environment).

For a general source installation, activate the chosen environment and run:

```sh
python -m pip install -e .
```

The Windows and Linux Python installations are separate. A Windows bundled
runtime does not supply Linux binaries. Manual mode uses the selected server
installation and does not install its dependencies. The remote interpreter's directory is added to the command search
path, so tools installed beside that interpreter are found without an interactive
Conda activation. Other tools must already be on the server account's `PATH`.

## Connect

Open the settings button beside the execution target and add a server:

| Field | Meaning |
|---|---|
| Name | A local display name |
| Host, port, username | The SSH endpoint and existing account |
| Server environment | Automatic deployment (new connections) or an existing environment |
| Installation directory | Optional absolute Linux path for a managed deployment; defaults to the server user's home |
| BioPipe directory | Absolute Linux path to the matching source checkout |
| Run directory | Absolute writable Linux directory for jobs and the server registry |
| Python | The environment's absolute Python executable, or `python3` on the remote PATH |
| Authentication | Password, a local private-key file, or SSH Agent |
| SSH gateway | Ordinary SSH by default; select interactive gateway for a numbered instance menu |

Passwords and key passphrases stay in process memory. They are never written to
connection records, workflow bundles or job logs. Closing Studio discards them.
Connection records contain paths, host information and the trusted public host
key. On first use, verify the displayed SHA-256 fingerprint against the server's
trusted identity; a changed key requires a new explicit trust action. The
interactive mode supports a shell or a simple numeric instance menu, not arbitrary
MFA, browser login or nested interactive questionnaires.

Control messages are compressed and checksummed. Short frames are acknowledged
individually, with bounded retries, so interactive gateways cannot silently
truncate a large registry or overflow the terminal input queue. This transport
format is independent of the operator and route protocols.

Connection profiles and cached catalogs are stored under the active Studio
profile's `.studio/remote/` directory. No installation path or account is built
into the application. The saved graph refers to the connection by its local ID:

```json
{"runtime":{"execution":{"kind":"ssh","profile_id":"<local-connection-id>"}}}
```

When importing on another Windows computer, create/select its own server profile
in the toolbar. Missing connections produce an error; execution never silently
falls back to the local machine. A disconnected server with a cached catalog
still supports editing and saving. Checking and running require a live connection.
Current workflow bundles retain `graph.json`, a separate `parameters.json` with
frozen Reader and operator values, and per-workflow `execution.json`. Earlier
two-file bundles remain readable. Existing code pins are retained and verified
against the server registry at submission.

## Files, memory and outputs

The file picker requests directory names and file metadata over SSH. It never
reads an entire input file to determine its size. Directory listings are paged;
hidden files can be shown explicitly. The account's existing filesystem access
determines which files it can use. Choosing a primary file selects its Reader;
companion-file and reference-genome parameters can also browse the server.
Relative server source paths resolve inside the server run directory. Absolute
paths can refer to data elsewhere on the server. In the current editor, local
file selections record their location explicitly and are automatically staged
when needed by a server operator. A path entered as a server path must exist on
that server; changing the preferred execution target does not relocate the file.

For server-resident inputs, submission sends workflow topology and parameter
values. Local inputs assigned to a server are transferred through the verified
upload cache before submission. The server writes
`task.yaml`, `parameters.json`, `plugins.lock.json` and `job.json` under
`<run-directory>/.studio/jobs/<job-id>/`. Reader execution, compressed-file handling,
file references, subprocess isolation, streaming, planned cache placement and
emergency spilling use the same existing engine.

The UI displays the server's memory pool. Current host admission takes one
available-memory snapshot for a host execution session and reserves 90% for its
shared pool. Workers receive individual shares or explicit requested budgets;
concurrent workers do not each receive the entire pool. No Windows RAM value is
substituted, and there is no periodic available-memory replanning. Runtime pressure still uses the
emergency spill mechanism. External programs retain their existing memory-limit
and chunk behavior; remote execution does not make an unsupported algorithm stream.
On Linux, the snapshot is capped by cgroup v1/v2 hard-limit headroom, including
visible parent groups. Charged file cache is conservatively counted as used memory.
This prevents a container from budgeting against its host's larger RAM pool.

Server outputs remain in their run directories. The task results panel can request
a preview, report or download. Mixed-environment stages transfer the intermediate
artifacts needed by downstream operators; they do not mirror the whole server
workspace. Diagnostic events and console logs return to the editor. The log panel
shows recent output; **Full process log** streams the complete server console in
chunks rather than truncating the archived log. A 128 MiB control-message guard
is a transport safeguard, not an input-data or file-upload limit.

## Disconnect, retry and stop

SSH starts a small bridge to a server-owned job service. The service listens on a
private Unix-domain socket with user-only permissions, not on a public HTTP port.
No inbound server port besides SSH is required. Its worker and watcher survive
closing Windows Studio or disconnecting SSH. Reconnect to the same workspace to
reload history and resume log viewing. Idle services exit after five minutes
without a running worker; job records and logs remain on disk.

A submission identity is persisted before sending a run request. If the response
is lost, retrying that unchanged submission returns the same server job rather
than launching it twice. Reusing that identity with another graph is rejected.
Current host admission permits concurrent tasks when memory and CPU reservations
fit; additional tasks queue. The task manager stops individual jobs. If SSH is
offline, cancellation remains pending until the server acknowledges it; a pending
request must not be presented as a confirmed stop. Disconnecting or removing a local connection
does not stop computation. Powering off the server still stops its processes;
this feature is not checkpoint/restart or a cluster scheduler.

During a source upgrade, let active jobs finish and allow the idle service to
exit before replacing its source, or use a new run directory. A workspace already
served from a different checkout is rejected rather than silently switching it.

## Catalog system compatibility

The projected registry contains `supported_systems` and `systems_status`; no v3
operator declaration or parameter protocol changes are required. These values
are derived from known dependencies and BioPipe's external-tool adapters.
The Hi-C BWA/samtools/pairtools/cooltools adapters select Linux; their library items
and canvas cards display **Linux**. This describes the supported adapter path,
not a claim that every upstream tool can never be ported to another OS.

Unknown or conditional dependencies have `systems_status: "unknown"`; their
candidate platform list is not a compatibility guarantee. Maintain recognized
capabilities in `biopipe/platforms.py`. Actual tool availability is returned by the
server connection handshake and executable validation remains at runtime.

## Implementation map

| Module | Responsibility |
|---|---|
| `biopipe/remote/protocol.py` | Framed, checksummed control messages that tolerate PTY banners and echo |
| `biopipe/remote/client.py` | SSH authentication, explicit host trust, ordinary/interactive transport |
| `biopipe/remote/provision.py` | Python-free bootstrap, source allowlist, verified download and installation progress |
| `biopipe/remote/install_linux.py` | Managed environment requirements, dependency and executable checks, readiness receipt |
| `biopipe/remote/server.py` | Private socket service, file metadata, detached jobs, resumable logs |
| `src/web/remote_service.py` | Local profiles, cached catalogs, remote job references and retry identities |
| `src/web/remote_api.py` | Local token-protected endpoints and log streaming |
| `frontend/src/RemotePanel.tsx` | Connection dialog and server file picker |
| `tests/test_remote.py` | Real loopback SSH plus remote routing/worker regression tests |

CLI/MCP canvas commands preserve the execution target. Agent validation and run
requests use the same routing as the UI, and still require the existing run scope.
The application never supplies an AI service or exposes the local agent API to
the server's public network.
