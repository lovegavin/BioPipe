# Application API, CLI and MCP

Operon has one application layer and three public integration surfaces:

| Surface | Responsibility |
| --- | --- |
| HTTP API | Versioned, structured workflows, tasks, artifacts and library discovery for software integrations |
| CLI | Reproducible commands, server/batch use and local library maintenance |
| MCP | Agent-oriented tools, progressive documentation discovery and optional canvas collaboration |

All three use the same workflow store, worker scheduler, parameter snapshots,
memory admission, spill store and SSH coordinator. MCP is not an AI provider.
Graph editing and task execution remain separate operations.

For a complete connection-to-result example, see the [third-party API tutorial](api_quickstart.md).
For agents, use the [installed three-layer guide](agent_operations.md).
For YAML-first batch use and environment configuration, follow the
[Linux server and terminal quickstart](server_cli.md), also available through
`operon help server`.

## Run without a desktop window

Install Operon normally; install the `agent` extra when MCP is required. There
is no frontend build or desktop dependency for headless execution.
Standard wheels include the analysis worker as `operon.worker`; they do not
require a source checkout or a `scripts/` directory. For a prepared task folder,
`python -m operon.worker /path/to/task --check` validates without executing,
and omitting `--check` runs it. Source checkouts retain `scripts/run.py` as a
compatible wrapper with the same memory overrides and logging behavior.

```text
operon --workspace /path/to/project workflow validate route.json --require-files
operon --workspace /path/to/project workflow save route.json
operon --workspace /path/to/project run route.json --request-id analysis-001
operon --workspace /path/to/project jobs get <job-id>
operon --workspace /path/to/project jobs logs <job-id> --follow
operon --workspace /path/to/project artifacts list <job-id>
operon --workspace /path/to/project artifacts report <job-id> 0 --output summary.json
```

Use the same workspace/profile selectors for every command. Relative input paths
are relative to the workflow's `base_dir` within the selected workspace, not the
terminal's current directory. Use an explicit workspace containing the inputs;
the existing data-root validation is not bypassed by the CLI. Self-contained
graph JSON and `.operon.zip` bundles are accepted. Saved JSON records containing
a `graph` member are also accepted. Portable workflow bundles preserve independent
parameter values but do not automatically contain large input datasets.
Public workflow YAML is also accepted. `--workspace .` resolves against the
terminal's current directory; YAML metadata sidecars resolve beside the YAML.
Use `environment check` for read-only route readiness, or explicit
`environment prepare` to install registered-provider dependencies. Blocked
readiness exits 1. `environment status` reports the live service interpreter.

The first command reuses a compatible running service or starts a hidden,
detached loopback service. The selected directory controls discovery; no fixed
port or machine-specific installation path is embedded. The service persists
after a CLI command or MCP connection exits, so submitted jobs continue.

```text
operon --workspace /path/to/project service status
operon --workspace /path/to/project service start
operon --workspace /path/to/project service stop
operon --workspace /path/to/project serve --port 0
```

`serve` is the foreground alternative for a process manager. `service status`
does not start anything. `service stop` refuses active tasks and cannot stop a
service owned by a desktop window. Cancel unwanted tasks explicitly, wait for
their terminal state, then stop. Each profile permits one detached service owner;
the operating-system lock is released after a crash. Diagnostics are written to
`<data>/service.log`. Application state lives in the same resolved profile used
by Studio; the standalone service never creates a fabricated canvas session.

`run --wait` optionally waits for completion; `--timeout` bounds the wait rather
than canceling the job. JSON results include terminal job status or
`wait_timed_out`. Submission acceptance alone does not mean scientific success.
With `--wait`, a successful run exits 0, a failed/cancelled/interrupted run exits
1, and an expired wait exits 124 while the task continues. Ordinary reads and
submission commands return their own operation status.

Startup and request polling read the compiled registry manifest, not operator
Python sources. Source scanning and compilation happen on explicit library
refresh. Workers still verify their pinned implementations before execution.

## Saved workflows and immutable run parameters

`workflow save` creates a reusable record. Updating it requires both `--id` and
`--expected-version`; a stale version returns `revision_conflict` without writing.
`workflow get <id>` returns hydrated values. The store persists topology,
`parameters/<id>/vN.json` and `execution/<id>/vN.json` separately, as in Studio.

```text
operon workflow prepare route.json
operon workflow export route.json --output route.operon.zip
operon workflow save changed.json --id <workflow-id> --expected-version 1
operon run --workflow <workflow-id> --expected-version 2 --request-id analysis-002
```

Each run freezes its graph, operator pins and its own `parameters.json`; later
defaults or saved-workflow edits do not change a submitted job. `prepare` freezes
defaults and pins without running computation. `validate` optionally checks file
existence; actual execution always validates its inputs again.

## Retry and failure behavior

Use a stable `request_id` for retries of the same submission. Identical retries
return the original job ID; a changed request with the same ID returns
`idempotency_conflict`. Receipts are profile-wide and persisted before launching.
A lost response can be reconciled against the durable job record. If the service
crashes in a gap where no job can be identified, it returns `submission_uncertain`
and preserves the receipt, rather than silently duplicating work. Inspect task
history before deliberately using a new request ID. This is an at-most-once
retry policy, not a promise of transactional execution across arbitrary tools.

Explicitly stopping the service differs from losing the CLI connection. On an
unexpected service restart the existing worker recovery policy applies: incomplete
local jobs become interrupted, while durable queued/coordinated tasks use their
existing recovery rules. No task is reported successful merely because its
launcher exited.

## HTTP contract

The public application prefix is `/api/v1`. Existing `/api/agent` canvas methods
remain available for desktop compatibility. An integration obtains the dynamically
discovered loopback URL and authenticates using the existing discovery exchange:
`POST /api/agent/connect`, followed by `Authorization: Bearer <token>`.
The Python `operon.client.Client` implements this exchange. Discovery credentials
are local secrets and must not be copied into agent prompts.

| Endpoint | Required capability | Purpose |
| --- | --- | --- |
| `GET /guides`, `/guides/{topic}` | context | Installed operating topics, version and conditional content hash |
| `GET /openapi.json` | context | Machine-readable application reference with Bearer authentication |
| `GET /capabilities` | context | API version and supported services |
| `GET /workflows`, `GET /workflows/{id}` | context | Saved workflows |
| `POST /workflows/prepare`, `/validate`, `/export` | context | Prepare, check, portable ZIP export |
| `POST /workflows` | edit | Create/update with `expected_version` |
| `POST /jobs` | run | Submit `{graph, request_id}` or `{workflow_id, expected_version, request_id}` |
| `GET /jobs`, `GET /jobs/{id}` | context | Durable status, progress and run provenance |
| `GET /jobs/{id}/parameters` | context | Frozen workflow parameter values, execution settings, memory configuration and pins |
| `POST /jobs/{id}/cancel` | run | Cancel through the original coordinator |
| `GET /jobs/{id}/logs` | context | Bounded log chunk and byte cursor |
| `GET /jobs/{id}/artifacts` | context | Artifact metadata and report links |
| `GET /jobs/{id}/artifacts/{artifact}/preview` | context | Bounded preview |
| `GET /jobs/{id}/artifacts/{artifact}/file` | context | Stream a retained artifact; optional file `role` |
| `GET /jobs/{id}/reports/{index}` | context | Original generated report |
| `GET /jobs/{id}/reports/{index}/figure` | context | Original figure selected by `format` and `figure_id` |
| `GET /operators` | context | Paged summaries and search filters |
| `POST /operators/describe` | context | Selected schemas and document sections |
| `GET /resources`, `GET /remotes` | context | Host resources and configured SSH connections |
| `POST /remotes`, `POST /remotes/{id}/trust` | edit | Connection configuration and explicit host trust |
| `POST /remotes/{id}/connect` | run | Connect the selected server |

Every path in the table is relative to `/api/v1`. Authentication applies to reads
as well as writes, including original output files. Headless hosting exposes no
frontend assets and no `/api/bootstrap` token-disclosure endpoint. It remains a
local single-user service, not an unauthenticated public server.

Logs use byte offsets with a bounded `limit` (up to 1 MiB per response); this is a
response window, not a file-size or job-size limit. `base64` permits lossless
reassembly when UTF-8 characters span chunks. `text` is for immediate display.
Artifact listing uses persisted metadata and does not load matrix contents;
explicit file copies stream to disk. Remote files continue using the existing
resumable transfer cache and memory accounting. Intermediates without a retained
file reference have `available: false`; files deleted outside Operon return a
missing-file error when opened and are never silently recomputed.
The index also exposes every registered figure ID/format with its original-file
link, physical dimensions and producing step. It uses figure metadata already
recorded in the run summary, without downloading reports merely to populate the
list. Historical jobs lacking that metadata retain their original report links.

HTTP defaults remain full for compatibility. `GET /operators?view=brief` returns
ranked compact summaries. Describe accepts `view=schema|docs|full`. Job reads accept
`view=brief|full`; logs accept `encoding=text|base64|both`. MCP/CLI use compact
discovery/status and text-only logs by default. `operon_job(wait_seconds=30)` and
`operon jobs wait <id> --timeout 30` wait without repeated model calls. Timeouts
never cancel or duplicate a submitted task.

## MCP without a canvas

Configure the existing `operon mcp` command. Add `--allow-run` to grant execution
within the user's authorized task; `--read-only` removes editing and
`--allow-plugins` separately grants installation. Window-independent tools include:

- `operon_operator_search`, `operon_operator_describe`;
- `operon_workflows`, `operon_workflow_save`, `operon_workflow_prepare`;
- `operon_submit`, `operon_jobs`, `operon_job`, `operon_logs`, `operon_cancel`;
- `operon_artifacts`.

Search returns summaries. Describe returns contracts, parameter schema and a
section index by default; request only needed sections, or `['*']` explicitly.
Pass a job's `plugins.generation` to describe its pinned documentation. Reading
documentation does not import operator implementations or install dependencies.

Canvas tools still read the user's real selection, apply revision-checked batches
and preserve one undo entry per batch. An empty session list is valid in headless
mode. Undo changes a graph; it neither reverses completed computation nor deletes
output files. The CLI and MCP never receive broader execution rights merely by
switching from a graph-editing endpoint to a task endpoint.

## SSH from the CLI

`servers list`, `servers save profile.json` and `servers connect <id>` use the same
connection registry as Studio. Host-key trust requires the actual fingerprint
reported by the connection handshake. Prefer an SSH key/agent; for a password,
`--credentials-stdin` accepts a JSON object from stdin so credentials are not
placed in process arguments. Saving connection profiles does not store passwords.
The workflow's independent execution settings determine local/remote placement;
upload, resumable reuse, host admission and route-node placement stay unchanged.
