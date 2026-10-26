# Connect your own agent: CLI, MCP and canvas context

BioPipe supplies local tools and semantic canvas state. It does not provide a model,
chat service or API-key store. Ask questions in your own agent client. An agent can
read the currently selected nodes, edit the graph and, when separately enabled,
start analysis jobs.

## Setup

Install the repository package in the Studio environment:

```text
python -m pip install -e ".[agent]"
```

Launch the desktop app or `python scripts/studio.py`, then open a canvas. Configure
a client supporting MCP stdio with:

```json
{
  "mcpServers": {
    "biopipe": {"command": "biopipe", "args": ["mcp"]}
  }
}
```

If the client does not inherit the environment's PATH, set `command` to that
environment's Python executable and use `args: ["-m", "biopipe", "mcp"]`.
This is a user-supplied runtime location, not a path embedded in BioPipe.
The current transport uses the Python MCP SDK v1 (`mcp>=1.20,<2`).

Default capabilities are `context` and `edit`: graph changes appear directly and
are undoable; editing never starts a job. Add `--allow-run` only when job execution
is intended. `--read-only` disables graph editing; `--allow-plugins` separately
permits installation of a selected local wheel. The desktop's Agent panel shows
connected clients and can revoke their tokens.

Example for a separate profile:

```json
{"mcpServers":{"biopipe":{"command":"biopipe","args":["--profile-dir","~/research-profile","mcp","--read-only"]}}}
```

Desktop, development server, CLI and MCP use the same profile resolver. The default
is `~/.biopipe/studio`; use `--workspace` only when Studio was launched with that
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

MCP instructions ask the agent to call `biopipe_context` before answering a canvas
question. Tools always read current state; BioPipe cannot force a particular client
to inject context automatically. This version exposes polling and resources, not
MCP resource-change subscriptions or unsolicited messages to a model. A client that
wants continuous awareness should poll events and refresh context when they change.

When nothing is selected, selection context is empty (`empty_selection: true`);
request `scope: "document"` explicitly for the full graph. With multiple active
windows, select `session_id`; do not guess which one the user meant. Old session
snapshots can remain on disk. Automatic selection prefers recently active windows;
the returned `updated_at` makes stale state visible.

## CLI

Commands return UTF-8 JSON on stdout; diagnostics/errors go to stderr. Global flags
`--profile-dir`, `--workspace`, `--instance`, `--session` and `--json` can appear
before or after subcommands. Replace placeholders below with IDs from the responses.

```text
biopipe sessions list
biopipe --session <session> context get
biopipe --session <session> context get --scope document
biopipe operators list
biopipe operators describe pca
biopipe graph validate route.json
biopipe --session <session> graph open route.json --expected-revision 4 --new-tab
biopipe --session <session> graph get
biopipe --session <session> graph apply commands.json --document <document> --expected-revision 5 --request-id edit-001
biopipe --session <session> graph undo --document <document> --expected-revision 6
biopipe --session <session> graph redo --document <document> --expected-revision 7
biopipe --session <session> events watch --after 0
biopipe --session <session> run --document <document> --expected-revision 8
biopipe jobs get <job>
biopipe jobs cancel <job>
```

The numbers illustrate sequential revisions; always use the actual returned value.
`graph open` creates a new tab without executing it. Positions may be omitted from
generated nodes; the service fills a deterministic DAG layout. A generated graph
must use known operator IDs, `kind`, `params`, sources and edge ports from the
[graph schema](../biopipe_sdk/schemas/graph.json). `graph validate` checks a complete
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
| `biopipe_sessions`, `biopipe_context`, `biopipe_graph` | Choose a window and read state |
| `biopipe_catalog`, `biopipe_validate` | Discover schemas and validate a graph |
| `biopipe_open`, `biopipe_apply`, `biopipe_undo` | New tab, transactional edit, undo/redo |
| `biopipe_events` | Poll changes after a cursor |
| `biopipe_run`, `biopipe_job`, `biopipe_cancel` | Explicit execution and job inspection |
| `biopipe_plugin_install` | Capability-gated local wheel installation |

Resources: `biopipe://selection`, `biopipe://sessions/{session_id}/selection`,
`biopipe://catalog`. Commands share the CLI's HTTP service and validations.
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
