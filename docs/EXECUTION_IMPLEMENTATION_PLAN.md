# Execution environments and resumable data movement

Implementation design and acceptance checklist. For verified behavior and user
instructions, see [Execution environments](EXECUTION_ENVIRONMENTS.md).

## Requirements

Local inputs can be sent to SSH execution automatically, with byte progress,
resumption, integrity checks and content-addressed reuse. Manual execution may
assign top-level operator nodes to local or SSH targets. Automatic execution
chooses eligible environments using data locality, dependency availability,
estimated transfer/compute cost and available admission capacity. A route node
is an atomic placement unit, including nested routes. Saved workflows retain
their own execution configuration independently of parameter defaults.

Multiple jobs may run concurrently only after machine-wide CPU/memory admission.
Analysis uses isolated processes (not Python CPU threads); transport and job
monitoring may use threads. Existing streaming, planned spill and emergency spill
remain the scientific runtime's responsibility. Unknown future external memory
pressure invokes emergency pressure handling rather than periodic replanning.

## Shared interfaces (implementation contract)

- TargetRef: `{kind: "local"}` or `{kind: "ssh", profile_id: "..."}`.
- `graph.runtime.execution`: existing `kind` / `profile_id` select the default
  target. Additional fields: `mode: "manual" | "auto"`, `node_targets` mapping
  top-level node IDs to TargetRef; `eligible_targets` TargetRef array (optional);
  `max_parallel_tasks` (positive integer, optional); `file_locations` mapping
  `nodeId.params.key` or `nodeId.source.args.key` to TargetRef. Missing mode on old
  graphs means manual with the existing whole-workflow target. New UI defaults
  to auto. Explicit selections never fall back silently to another machine.
- Source gets optional `location: TargetRef`. Missing location on an older graph
  means its whole-workflow target; local upload always sets `{kind:"local"}`.
- `POST /api/execution/plan` accepts Graph and returns `{mode, units, transfers,
  warnings}`. Unit: `{id, node_ids, target, reason, estimated_bytes}`. No upload or
  scientific execution occurs during a preview.
- Existing `/api/jobs` is the submission/history API. New active statuses include
  `queued`, `preparing`, `uploading`, `running`, `waiting_connection`; terminal statuses stay unchanged.
  Jobs may have `progress: {phase, completed, total, percent?, bytes_done?,
  bytes_total?, current?}`, `allocation`, `children`, `execution_plan`.
- `GET /api/execution/resources` reports local and connected target admission
  state. Cancellation applies to queue, transfers and running children.
- Transfers are chunked, bounded and checksummed. Destination paths are created
  only inside an owned cache. Receipts/part files survive reconnect. A complete
  file is published atomically only after full content verification. Source
  mutations, corruption, symlink escapes and disk exhaustion must fail safely.
- Per-workflow `execution.json` sidecars contain memory and execution settings;
  bundles include this beside graph.json and parameters.json. Existing two-file
  bundles remain importable. Saved settings and run snapshots are immutable by
  version, and changes in another document do not mutate them.

## Ownership during implementation

1. Transfer layer: remote transfer store/RPC, local transfer client/receipts/tests.
2. Admission: JobService queue/parallel jobs, CPU and memory reservation, runtime
   budget handoff and resource tests. Preserve existing launch/logging contracts.
3. Frontend: inspector grouping, per-document execution controls/context menu,
   source location, task manager/progress and UI tests.
4. Integration: execution planner/orchestrator, portable intermediate artifacts,
   saved config/bundles, API wiring, compatibility, docs and end-to-end testing.

## Acceptance

- Interrupted upload resumes without retransmitting its verified prefix; repeated
  inputs reuse complete content; changed/corrupt content cannot reuse a receipt.
- Whole remote graph with local data and reference/companion files runs normally.
- Local -> SSH -> local DAG retains Form info/axis_info, file-backed artifacts,
  parameter snapshots and logs. No pickle is accepted across an SSH boundary.
- Automatic placement rejects missing capabilities and exposes reasons; manual
  node choices are disabled in automatic UI and route internals cannot split.
- Concurrent jobs never reserve more than the host's startup memory capacity;
  excessive requests queue or fail clearly. Cancellation releases reservations
  exactly once, and restart reconciles unfinished jobs.
- Every document's saved config round-trips independently; methods/required
  parameters precede collapsed execution/resource fields.
- Existing Python/frontend regression, actual desktop launch and synthetic SSH
  integration pass before any release is considered.
