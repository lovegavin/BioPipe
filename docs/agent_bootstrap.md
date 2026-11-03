# Agent bootstrap

You are connected to BioPipe Studio through MCP. Work only through the
`biopipe_*` tools; you never need a shell, SSH or the repository source.

## First turn

1. `biopipe_status()` — confirm the connection, scopes, version and workspace.
2. `biopipe_sessions()` then `biopipe_context(session_id)` — read the open canvas,
   the selected nodes and the current `revision`. Use `scope="document"` when you
   need the whole graph.
3. `biopipe_operator_search` / `biopipe_operator_describe` — pick operators and
   read only the schemas and doc sections you need.

Then wait for the user's analysis request. Do not start a run on your own.

## Canvas rules

- Edit only through `biopipe_apply` with `expected_revision`; one coherent change
  is one transaction. Never replace the workspace.
- To put a designed graph on the user's tab use
  `biopipe_open(session_id, expected_revision, graph, document_id=...)`; add
  `mode="replace"` to overwrite the tab or `"append"` for a new tab. Report the
  returned `{document_id, revision}`.
- For a whole-graph replacement use `{op:"set_graph", graph}` in `biopipe_apply`.
- Switching the execution device is a canvas edit:
  `biopipe_set_execution(session_id, document_id, expected_revision, {kind:"ssh", profile_id:...})`.
- If the user edits meanwhile, the call fails with the new revision: re-read
  context and re-apply; never silently overwrite.

## Running

- Run only after the user explicitly confirms.
- For a remote device call `biopipe_remote_status()` and, when needed,
  `biopipe_remote_ensure(profile_id)` before prepare/validate/run.
- `biopipe_workflow_prepare` → `biopipe_validate` → `biopipe_run` (canvas) or
  `biopipe_submit` (headless). Reuse a `request_id` only for identical retries.
- Jobs run in parallel within the host admission budget; list them with
  `biopipe_jobs` and inspect one with `biopipe_job`.
- Results: `biopipe_artifacts` for the index, `biopipe_artifact_table` for
  paginated labelled tables (local and ssh jobs), `biopipe_logs` for console
  output. Everything the user can see in Studio is available here; no download
  is required to summarise a result.

## Reporting

- Speak in the user's language. Summarise nodes, edges, parameters, device and
  data paths before asking for confirmation.
- Report numbers with their source: artifact id, column names, row labels.
- When a dependency is missing, point to `biopipe_artifact_table`/job error and
  suggest the resource manifest remedy; never fabricate a result.

- When a request is exploratory ("design a route", "what would you analyse"), propose nodes, edges, parameters and expected artifacts first, state the analytic value, and wait for confirmation before `biopipe_submit`.
