# Prepare and run without a window

## Reuse a saved workflow

Call `biopipe_workflows()` and retrieve the chosen ID. If its frozen parameters
and inputs already fit, submit with `biopipe_submit(workflow_id=..., expected_version=...,
request_id=...)`. Use the actual version. To change it, modify the hydrated graph,
prepare/check it, then save with workflow_id and expected_version. Never replace
saved values with defaults from a refreshed library.

## Create a route

Read the operators guide. Use `biopipe schema graph` for the JSON contract. Minimal
example for an existing CSV named input.csv in the selected workspace:

```json
{"schema_version":2,"name":"CSV summary","base_dir":".",
 "nodes":[
   {"id":"input","kind":"source","source":{"path":"input.csv","dims":["sample","feature"],"labels":{"sample":"auto","feature":"builtin"}}},
   {"id":"summary","kind":"operator","operator":"describe","params":{}}
 ],"edges":[{"id":"e1","source":"input","target":"summary"}]}
```

Keep the user's memory and runtime.execution settings when modifying a route.
Positions may be omitted. Relative inputs resolve against graph.base_dir within
the selected workspace, not the agent shell's current directory.

- MCP: `biopipe_workflow_prepare(graph, require_files=true)` freezes defaults/pins
  and validates in one tool call. It does not run. Inspect validation; a second
  identical biopipe_validate call is unnecessary. Save if reuse is desired, then
  submit the returned graph with a unique, stable request_id.
- CLI: `biopipe --workspace <project> workflow prepare route.json --require-files
  --output prepared.json` prepares, checks and writes a reusable graph (one line).
  Then `biopipe --workspace <project> run prepared.json --request-id analysis-001
  --wait --timeout 60 --brief`. A timeout leaves the job running; keep its ID.

Missing files/dependencies or schema errors require correction, not repeated
submission. Keep one workspace/profile selection across all calls. Saved routes
and every submitted job retain independent parameter JSON. See jobs/results next.
