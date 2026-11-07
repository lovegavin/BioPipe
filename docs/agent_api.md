# Connect your own agent: CLI, MCP and canvas context

Operon supplies local tools and semantic canvas state. It does not provide a model,
chat service or API-key store. Ask questions in your own agent client. An agent can
read the currently selected nodes, edit the graph and, when separately enabled,
start analysis jobs.

For the operating sequence and small-response defaults, start with the
[three-layer agent guide](agent_operations.md), available in every installation
as `operon help` / `operon_guide`. For a non-agent application use the
[API tutorial](api_quickstart.md).

## Setup

Install the repository package in the Studio environment:

```text
python -m pip install -e ".[agent]"
```

The desktop is optional. CLI and MCP reuse a running application service or start
a detached headless service automatically. Open a Studio canvas only when you
want selection context and live canvas editing. See [the application API and
headless workflow guide](headless_api.md) for standalone workflows, jobs and
artifacts. Configure a client supporting MCP stdio with:

```json
{
  "mcpServers": {
    "operon": {"command": "operon", "args": ["mcp"]}
  }
}
```

If the client does not inherit the environment's PATH, set `command` to that
environment's Python executable and use `args: ["-m", "operon", "mcp"]`.
This is a user-supplied runtime location, not a path embedded in Operon.
The current transport uses the Python MCP SDK v1 (`mcp>=1.20,<2`).

Default capabilities are `context` and `edit`: graph changes appear directly and
are undoable; editing never starts a job. Add `--allow-run` only when job execution
is intended. `--read-only` disables graph editing; `--allow-plugins` separately
permits installation of a selected local wheel. The desktop's Agent panel shows
connected clients and can revoke their tokens.

Example for a separate profile:

```json
{"mcpServers":{"operon":{"command":"operon","args":["--profile-dir","~/research-profile","mcp","--read-only"]}}}
```

Desktop, development server, CLI and MCP use the same profile resolver. The default
is `~/.operon/studio`; use `--workspace` only when Studio was launched with that
same isolated workspace. Servers publish authenticated discovery records under
`<data>/agent/servers/`. Ports are discovered dynamically and remain loopback-only.
Process identity is checked; an authenticated instance handshake supports agent
sandboxes that cannot inspect the desktop process table.

The Agent panel generates a configuration using the actual interpreter and resolved
workspace/data directory. This is convenient for isolated workspaces and clients
with a different PATH. Regenerate that configuration after moving the installation.
`--data-dir` is available with an explicit `--workspace` for explicitly selected layouts.

## Selection context

The UI publishes active document, selected nodes/edges, inspected node, focused
field ID and viewport. Context includes selected nodes plus immediate neighbors,
parameters, relevant connections, input/output contracts, memory settings, graph
revision and plugin pins. It does not send tensor contents. Node parameters may
include input paths and user-supplied labels, so share a copied context intentionally.

Single-click selects; double-click opens the inspector. Select several nodes with
Ctrl-click or Shift selection. Use **Agent → Copy selection context**, or the canvas
context menu, to paste the JSON into a client without MCP.

An empty canvas-session list is normal without Studio; use `operon_workflows`
and `operon_submit` instead of inventing a canvas session. MCP instructions ask
the agent to call `operon_context` before answering a canvas
question. Tools always read current state; Operon cannot force a particular client
to inject context automatically. This version exposes polling and resources, not
MCP resource-change subscriptions or unsolicited messages to a model. A client that
wants continuous awareness should poll events and refresh context when they change.

When nothing is selected, selection context is empty (`empty_selection: true`);
request `scope: "document"` explicitly for the full graph. With multiple active
windows, select `session_id`; do not guess which one the user meant. Old session
snapshots can remain on disk. Automatic selection prefers recently active windows;
the returned `updated_at` makes stale state visible.

## CLI

`graph open` and `graph validate` accept self-contained graph JSON or portable
`.operon.zip` bundles (`graph.json` plus `parameters.json`). Context/graph responses
always contain hydrated values. Agent-triggered jobs use the same independent
parameter snapshot as desktop-triggered jobs. See
[workflow parameter values](workflow_parameters.md).

Commands return UTF-8 JSON on stdout; diagnostics/errors go to stderr. Global flags
`--profile-dir`, `--workspace`, `--instance`, `--session` and `--json` can appear
before or after subcommands. Replace placeholders below with IDs from the responses.

```text
operon sessions list
operon --session <session> context get
operon --session <session> context get --scope document
operon operators list
operon operators describe pca
operon operators search --query "principal components"
operon operators describe pca --section parameters
operon workflow validate route.json --require-files
operon run route.json --request-id analysis-001
operon jobs logs <job> --follow
operon artifacts list <job>
operon graph validate route.json
operon --session <session> graph open route.json --expected-revision 4 --new-tab
operon --session <session> graph get
operon --session <session> graph apply commands.json --document <document> --expected-revision 5 --request-id edit-001
operon --session <session> graph undo --document <document> --expected-revision 6
operon --session <session> graph redo --document <document> --expected-revision 7
operon --session <session> events watch --after 0
operon --session <session> run --document <document> --expected-revision 8
operon jobs get <job>
operon jobs cancel <job>
```

The numbers illustrate sequential revisions; always use the actual returned value.
`graph open` creates a new tab without executing it. Positions may be omitted from
generated nodes; the service fills a deterministic DAG layout. A generated graph
must use known operator IDs, `kind`, `params`, sources and edge ports from the
[graph schema](../operon_sdk/schemas/graph.json). `graph validate` checks a complete
pipeline; editing permits incomplete drafts but rejects cycles and known incompatible
connections. File existence and real values are checked again when running.

`events watch` produces JSONL change batches with a monotonic cursor. The rolling
log retains 200 events; `reset: true` means the client must reread a snapshot.
Exit codes: `0` success, `2` invalid request/tool failure, `3` revision conflict,
`4` no connection or ambiguous session, `130` interrupted.

## Atomic edit commands

`commands.json` is a list or `{ "commands": [...] }`:

```json
[
  {"op":"update_node","id":"pca","patch":{"params":{"dim":"feature","n_components":3,"output":"pcs"}}},
  {"op":"configure","patch":{"name":"PCA with three components"}}
]
```

Each batch contains 1–200 commands and is one undo entry. `update_node.patch` is a
shallow patch: a supplied `params` object replaces that entire object. Read current
parameters first and preserve values you are not changing.

| Command | Required payload |
| --- | --- |
| `add_node` | `node`: source/operator/route node |
| `update_node` | `id`, `patch`; node ID and kind cannot be changed |
| `remove_node` | `id`; connected edges are removed too |
| `connect` | `edge`: unique ID, source/target, optional port handles |
| `disconnect` | Edge `id` |
| `configure` | `patch` containing only `name`, `memory`, `base_dir` |

Every write requires `expected_revision`. A stale revision fails with HTTP 409 and
`revision_conflict`, with no partial mutation. Reread context and reconcile the
intent before retrying. Presence/viewport changes have a separate `ui_revision` and
do not invalidate graph edits. An optional `request_id` makes identical retries
idempotent (100 recent receipts); reusing it for different edits fails.

The UI and agent use the same bounded history, up to 30 graph changes per document.
Undo/redo does not delete output files or reverse an executed analysis. Concurrent
unsent UI edits are preserved in a recovery tab instead of overwriting an agent
change; a local backup is retained if the 20-tab limit prevents recovery.

## MCP tools and resources

| Tools | Purpose |
| --- | --- |
| `operon_guide` | One installed task guide, topic index or conditional cached read |
| `operon_sessions`, `operon_context`, `operon_graph` | Choose a window and read state |
| `operon_catalog`, `operon_validate` | Discover schemas and validate a graph |
| `operon_open`, `operon_apply`, `operon_undo` | New tab, transactional edit, undo/redo |
| `operon_events` | Poll changes after a cursor |
| `operon_run`, `operon_job`, `operon_cancel` | Explicit execution and job inspection |
| `operon_plugin_install` | Capability-gated local wheel installation |
| `operon_operator_search`, `operon_operator_describe` | Paged discovery and selected documentation sections |
| `operon_workflows`, `operon_workflow_save`, `operon_workflow_prepare` | Workflows independent of canvas sessions |
| `operon_submit`, `operon_jobs`, `operon_logs`, `operon_artifacts` | Headless execution, status, log cursors and result links |

Resources: `operon://selection`, `operon://sessions/{session_id}/selection`,
`operon://catalog`, `operon://guide`, `operon://guide/{topic}`.
Commands share the CLI's HTTP service and validations.
MCP stdout is reserved for JSON-RPC; logs stay on stderr.

## Local HTTP gateway

The gateway lives at `/api/agent`. A discovery credential is exchanged at
`POST /connect` for a per-client bearer token and scopes. Tokens remain local;
do not paste discovery secrets into prompts. Context and catalog reads require
authentication, as do mutations. Main endpoints:

```text
GET  /sessions
GET  /sessions/{id}
GET  /sessions/{id}/context?scope=selection
POST /sessions/{id}/apply
POST /sessions/{id}/open
POST /sessions/{id}/undo
GET  /sessions/{id}/events?after=0
GET  /sessions/{id}/stream?after=0     SSE
POST /sessions/{id}/run
GET  /catalog
POST /validate
GET  /jobs/{id}
POST /jobs/{id}/cancel
```

UI-only sync/presence operations cannot be called by an ordinary agent token.
Revocation also stops an established SSE stream. This is a local integration
boundary, not a multi-user network service or a sandbox against malicious code
already running as the same OS user.
