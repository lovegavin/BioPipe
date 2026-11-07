# Server and batch workflows

Use the same selected Python and workspace for all commands. No desktop is needed.

1. `operon --workspace . workflow lint workflow.yaml` checks authoring syntax offline.
2. `operon --workspace . environment status` returns the live service interpreter,
   workspace and resources. It may start a headless service.
3. `operon --workspace . environment check workflow.yaml --require-files` checks
   only this route. Readiness blocked means exit 1; no installation occurs.
4. With the user's authorization, `environment prepare workflow.yaml` prepares
   registered-provider dependencies. Inline-script missing dependencies currently
   require explicit environment preparation or promotion to a provider.
5. `operon --workspace . run workflow.yaml --progress --brief --request-id KEY`
   waits; JSON stays on stdout and progress goes to stderr. Run never auto-installs.
6. Use `jobs get ID`, `jobs logs ID --follow`, and `artifacts list ID`. Use a new
   request ID for a changed workflow. Reusing the same ID is submission idempotency,
   not per-node checkpoint resume.

`service stop` refuses active jobs. To change the service interpreter, finish or
cancel tasks, stop, then restart with the selected Python. `service status` never
starts anything. `jobs wait ID --timeout 60` exits 124 on timeout without cancelling.
Keep independent `parameters.json` and `execution.json` files beside your YAML;
sidecar paths are project-relative, input data paths are workspace-relative.

The Linux server shares memory admission, spill and streaming with local execution.
SSH clients require `workflow_readiness` from 3.0 servers. Older servers need one
explicit upgrade, never a silent overwrite at connection. See `docs/server_cli.md`
in the distribution for installation, registration, exit codes and acceptance.
