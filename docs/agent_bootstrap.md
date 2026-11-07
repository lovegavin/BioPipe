# Agent bootstrap

You are connected to Operon Studio through MCP. Work only through the
`operon_*` tools; you never need a shell, SSH or the repository source.

## First turn

1. `operon_status()` — confirm the connection, scopes, version and workspace.
2. `operon_sessions()` then `operon_context(session_id)` — read the open canvas,
   the selected nodes and the current `revision`. Use `scope="document"` when you
   need the whole graph.
3. `operon_operator_search` / `operon_operator_describe` — pick operators and
   read only the schemas and doc sections you need.

Then wait for the user's analysis request. Do not start a run on your own.

## Canvas rules

- Edit only through `operon_apply` with `expected_revision`; one coherent change
  is one transaction. Never replace the workspace.
- To put a designed graph on the user's tab use
  `operon_open(session_id, expected_revision, graph, document_id=...)`; add
  `mode="replace"` to overwrite the tab or `"append"` for a new tab. Report the
  returned `{document_id, revision}`.
- For a whole-graph replacement use `{op:"set_graph", graph}` in `operon_apply`.
- Switching the execution device is a canvas edit:
  `operon_set_execution(session_id, document_id, expected_revision, {kind:"ssh", profile_id:...})`.
- If the user edits meanwhile, the call fails with the new revision: re-read
  context and re-apply; never silently overwrite.

## Running

- Run only after the user explicitly confirms.
- For a remote device call `operon_remote_status()` and, when needed,
  `operon_remote_ensure(profile_id)` before prepare/validate/run.
- `operon_workflow_prepare` → `operon_validate` → `operon_run` (canvas) or
  `operon_submit` (headless). Reuse a `request_id` only for identical retries.
- Jobs run in parallel within the host admission budget; list them with
  `operon_jobs` and inspect one with `operon_job`.
- Results: `operon_artifacts` for the index, `operon_artifact_table` for
  paginated labelled tables (local and ssh jobs), `operon_logs` for console
  output. Everything the user can see in Studio is available here; no download
  is required to summarise a result.

## Reporting

- Speak in the user's language. Summarise nodes, edges, parameters, device and
  data paths before asking for confirmation.
- Report numbers with their source: artifact id, column names, row labels.
- When a dependency is missing, point to `operon_artifact_table`/job error and
  suggest the resource manifest remedy; never fabricate a result.

- When a request is exploratory ("design a route", "what would you analyse"), propose nodes, edges, parameters and expected artifacts first, state the analytic value, and wait for confirmation before `operon_submit`.

- `operon_status` exists from Operon 1.119; on older servers use `operon_sessions` and `operon_context`.
