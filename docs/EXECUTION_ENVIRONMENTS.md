# Execution environments, transfers and concurrent tasks

Studio can edit a workflow on Windows while its operators run locally, on a
connected Linux server, or in successive stages on both. Input files have their
own locations. Selecting a server as the execution target does not require
moving those files by hand.

This guide describes the v0.8.1 desktop implementation. For SSH connection
setup, host-key verification and automatic Linux deployment, see
[Windows editing and SSH execution](REMOTE_EXECUTION.md). Both Lite and bundled
Windows archives include the mixed-environment task coordinator described here.

## Choose where a workflow runs

Open **Execution settings** from the canvas toolbar. Each open workflow owns its
settings; changing one page does not change another page or a submitted run.

| Setting | Behavior |
| --- | --- |
| Automatic | Select compatible environments using input locality, transfer estimates and queue pressure. New empty canvases use this mode. |
| Manual | Use the default environment, with explicit overrides for individual top-level operators. |
| Default/preferred environment | The toolbar target is the default in manual mode and a tie-breaking preference in automatic mode. |
| Parallel task limit | Limits concurrently submitted stages of this workflow and informs its automatic resource share. Host admission can permit fewer. |
| Preview environment assignment | Show the proposed stages, destinations, transfer count and warnings before submission. |

In manual mode, right-click an operator and select **Local**, a configured
server, or **Follow default**. The selected choice has a check mark. In automatic
mode these menu choices are disabled. Explicit manual choices never silently
fall back to a different machine. A missing connection, unsupported system or
unavailable required executable produces an error.

A **route operator is atomic**: its complete internal graph runs in one
environment. The outer canvas cannot split its internal operators between
machines. Opening that route for editing creates an editable graph; it does not
change the version snapshot already inserted in another workflow.

The library combines the local catalog with connected-server catalogs for
discovery. A visible library item is not proof that every machine can run it.
Planning checks the selected machine's catalog, supported systems, executable
tools and reported dependency state. Stage submission also resolves the saved
implementation pins on that machine.

### Automatic planning is bounded

The planner visits the DAG in topological order and performs four forward/reverse
placement sweeps over eligible environments. It does not enumerate all possible
assignments. Large known inputs favor nearby computation; unknown intermediate
sizes receive a nonzero transfer estimate. Queue pressure contributes a modest
cost, and the preferred environment breaks ties. This is a deterministic
heuristic, not a globally optimal schedule or a wall-clock runtime prediction.

The plan is fixed for that submission. Actual scientific data sizes still refine
the existing memory planner's step admission. Transient machine pressure uses
emergency spill and admission queues, rather than continuously moving operators
between hosts. A Linux badge identifies the supported execution path for the
operator; it is not a new field in the v3 authoring protocol.

## Select local or server inputs

The input inspector offers **Local file** even when the preferred execution
environment is a server. Local selections are imported into the Studio workspace
and explicitly marked as local. **Server file** browses names and metadata over
SSH and records the selected connection. The **File location** selector also
supports entering a path directly.

Reader companion sets retain their existing rules: for example, select PLINK
`.bed`, `.bim` and `.fam` together. Reference and companion path parameters have
local/server file controls too. Raw reference imports do not need a registered
Reader for that extension. The owning account must have permission to read every
input and write the destination workspace.

Submission stages the files needed by each destination before starting its
scientific child task. This includes declared Reader companions, supported
adjacent index files, and declared path parameters. It does not recursively upload
the input directory. File size comes from metadata, not loading the data into RAM.
Checksum verification reads files incrementally and therefore still takes I/O
time for a large file.

### Resumption and reuse

- Transfers use bounded chunks and checksums. A complete object becomes visible
  only after full verification and atomic publication.
- A disconnected upload retains its acknowledged prefix. Retrying verifies that
  prefix before continuing. Reconnecting resumes the coordinator's pending work.
- A complete, verified object can be reused across submissions. A repeated run
  can still spend time hashing the source and validating a cache hit.
- A source changed during transfer, a mismatched receipt, corrupted bytes or
  insufficient disk space produces a clear failure instead of silently using
  incomplete data.

Partial files, receipts and complete objects live in owned transfer caches.
These caches are separate from a scientific job's spill store. A workflow bundle
does not contain datasets or transfer-cache contents. Retained transfer objects
can use significant disk space; automatic quota-based eviction is not part of
this implementation. Do not remove a cache while a task is using it.

Inputs already on the execution server are used there. In a mixed workflow,
intermediate data crosses a boundary only when needed by a stage on another host.
SSH-to-SSH transfers are relayed through the editor's owned disk cache. A wholly
server-based workflow keeps its scientific inputs and outputs on that server;
opening a preview or downloading a result is a separate request.

## Stage boundaries preserve data contracts

Consecutive compatible placements form stages. Dependencies between stages come
from the original DAG, so independent stages can be prepared or submitted in
parallel. Each stage uses the ordinary worker process, independent parameter
snapshot, plugin lock and resource runtime.

Boundary outputs are explicitly retained until a portable handoff is published.
Handoffs use tagged JSON, numeric array files and verified file blobs; Python
pickle objects are not accepted across SSH boundaries. Forms retain their
dimensions, labels, `info` and `axis_info`. File artifacts retain their roles and
receive new fingerprints for their destination paths.

Receiving a handoff uses the existing managed-source machinery. Supported numeric
matrices can be read in bounded chunks from disk. A stage boundary does not make
an arbitrary full-memory operator streamable, and does not add CUDA support to
operators that lack it.

## Shared memory and CPU admission

Each machine has a resource pool shared by BioPipe launchers under the **same
operating-system user**. At the start of a new host execution session, BioPipe
takes one available-memory snapshot and assigns 90% as the host pool. Linux
container limits constrain that snapshot. The Windows budget is never substituted
for the server's budget.

An automatic task receives a share of that pool, with headroom for the worker and
its declared workspace. The requested parallel-task setting and available CPU
capacity influence the automatic share. Resource reservations also bound the
number of jobs actually admitted, so submitting several tasks does not grant each
one 90% of host RAM. Transport buffers have separate bounded reservations.

An explicit per-task budget remains explicit. If it occupies almost the whole
pool, other jobs wait. Lower the budget or use automatic allocation to allow more
concurrency. Disabling managed memory requires exclusive host admission. Requests
larger than the host capacity fail clearly. The task panel shows available pool
capacity, active work and queued work for each connected machine.

Within an admitted scientific process, BioPipe retains planned spill, disk-backed
sources, streaming capabilities, size corrections and emergency spill. The host
also monitors worker-tree memory, including child tools. If emergency spill cannot
recover from sustained pressure beyond a reservation, that task can be stopped to
protect other admitted tasks. A plugin's temporary native allocation cannot
always be intercepted before it occurs.

This pool does not coordinate other operating-system users or unrelated software.
It is not a cluster scheduler or a GPU scheduler. Independent scientific workers
use processes; transport and monitoring may use threads. A stage's scientific
operators retain their fixed execution order.

## Manage running tasks

The toolbar **Tasks** button opens the task manager. The canvas remains editable
after submission, and another document can be opened, saved or run while earlier
jobs continue. Each submitted task uses its saved snapshot.

Tasks show resource waiting, preparation, transfer, execution, connection waiting
and terminal states. During transfers, progress includes acknowledged bytes;
during execution it counts completed scientific steps, including steps inside
route operators. Internal stage jobs are grouped under their workflow, including
after SSH reconnection. Percentages are phase-specific, not
an estimated time to completion. Select a task to inspect its results or logs,
or stop that individual task without cancelling unrelated jobs.

SSH disconnection does not stop a server-owned scientific process. The local
coordinator waits for the connection before collecting new logs, moving data or
submitting a dependent stage. Reconnect the same profile and workspace. Completed
stage records and transfer receipts survive reopening Studio; submissions use
stable identities to avoid starting the same child twice after a lost response.

**A cancellation request is not a stop confirmation.** If the server is offline,
the parent task stays in a connection-waiting state with cancellation pending.
It can be reported as stopped only after the outstanding child cancellations
have been acknowledged. Disconnecting a profile and cancelling a task are
different actions.

Closing Studio stops its local workers. An interrupted scientific stage does not
resume inside a Python or external-tool call; it may need a fresh submission.
Only completed stage boundaries and verified transfer state are recoverable.
Powering off the execution server stops its processes.

## Workflow settings and frozen JSON values

A saved workflow bundle contains three inspectable files:

| File | Contents |
| --- | --- |
| `graph.json` | Topology, data-source definitions, route interfaces and implementation pins |
| `parameters.json` | Frozen concrete values for operators, Reader arguments and nested routes |
| `execution.json` | This workflow's memory and execution settings, including nested-route configuration snapshots |

Saved route versions store separate parameter and execution sidecars. Changing
defaults in an operator's `*.parameters.json`, editing another document, or
changing the preferred server does not rewrite an already submitted task.
Import still accepts older bundles containing only `graph.json` and
`parameters.json`; missing execution mode retains the older manual/default-target
behavior. Imported connection IDs must refer to profiles on the receiving
computer. Remap missing profiles explicitly before running.

The UI/API graph carries hydrated settings under `runtime.execution`. For example:

```json
{
  "kind": "local",
  "mode": "manual",
  "max_parallel_tasks": 2,
  "node_targets": {
    "align": {"kind": "ssh", "profile_id": "compute"}
  },
  "file_locations": {
    "align.params.reference": {"kind": "local"}
  }
}
```

`kind`/`profile_id` specify the default target; `node_targets` maps **top-level**
node IDs to targets. `eligible_targets` can optionally restrict automatic choices.
Each source can have a `location` target. Path selections use
`<node-id>.params.<key>` or `<node-id>.source.args.<key>` in `file_locations`.
Changing execution placement does not change the recorded location of an input.

No new operator declaration protocol is required. The inspector groups fields
using generic parameter semantics: method and required analysis choices appear
first; environment, tool and resource fields are collapsed. Authors should keep
using the documented v3 parameter schema. See
[workflow values](workflow_parameters.md) and [operator protocol](operator_protocol.md).

## Integration entry points

- `POST /api/execution/plan`: preview placement without executing analysis.
- `GET /api/execution/resources`: host pool snapshots and reservations.
- `POST /api/jobs`: submit the complete graph; normal job history, event streams
  and cancellation endpoints also cover coordinated tasks.
- `src/web/execution_plan.py`: bounded placement heuristic.
- `src/web/execution.py`: durable parent tasks, stages and data movement.
- `src/web/admission.py`: shared host resource reservations.
- `src/web/transfers.py` and `biopipe/remote/transfers.py`: verified resumable files.
- `biopipe/exchange.py`: portable scientific handoffs and managed-source loading.

These APIs retain Studio's local access controls. SSH credentials stay in the
connection session and do not belong in graph files, parameter files or logs.
