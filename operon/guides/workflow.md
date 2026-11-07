# Prepare and run without a window

## Reuse a saved workflow

Call `operon_workflows()` and retrieve the chosen ID. If its frozen parameters
and inputs already fit, submit with `operon_submit(workflow_id=..., expected_version=...,
request_id=...)`. Use the actual version. To change it, modify the hydrated graph,
prepare/check it, then save with workflow_id and expected_version. Never replace
saved values with defaults from a refreshed library.

## Create a route

Read the operators guide. Use `operon schema graph` for the JSON contract. Minimal
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

- MCP: `operon_workflow_prepare(graph, require_files=true)` freezes defaults/pins
  and validates in one tool call. It does not run. Inspect validation; a second
  identical operon_validate call is unnecessary. Save if reuse is desired, then
  submit the returned graph with a unique, stable request_id.
- CLI: `operon --workspace <project> workflow prepare route.json --require-files
  --output prepared.json` prepares, checks and writes a reusable graph (one line).
  Then `operon --workspace <project> run prepared.json --request-id analysis-001
  --wait --timeout 60 --brief`. A timeout leaves the job running; keep its ID.

Missing files/dependencies or schema errors require correction, not repeated
submission. Keep one workspace/profile selection across all calls. Saved routes
and every submitted job retain independent parameter JSON. See jobs/results next.

## Prepare missing dependencies explicitly

Check `readiness.status` after validation. `blocked` means the selected runtime
is not ready; inspect only its `blocked` entries. Validation, graph preparation,
registration and Run do not install dependencies. Readiness is tied to the route,
selected environment and dependency state, so validate again after relevant edits.

When the user has authorized installing/repairing this route's environment:

- MCP: `operon_workflow_prepare_environment(graph)` requires a connection started
  with `operon mcp --allow-plugins`. `--allow-run` alone is insufficient. This tool
  never broadens its own scopes; permission denial is not a reason to reconnect
  with broader permissions without authorization.
- CLI: `operon --workspace <project> workflow prepare-environment route.yaml`
  explicitly grants this invocation installation scope. JSON and workflow bundles
  are also accepted. It checks only the route's declared dependencies on its
  selected local/SSH environments, not every installed operator.

Preparation returns readiness without submitting a job. Revalidate with file
checks and submit separately when ready and authorized to run. Installations may
take several minutes; the preparation transport waits up to 30 minutes. A timeout
or disconnect does not prove installation failed: reconnect and validate current
status before deciding whether another explicit repair is needed. Do not blindly
repeat the installer or dump the complete catalog to diagnose one missing package.
