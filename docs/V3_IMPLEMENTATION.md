# BioPipe 3.0 implementation candidate

This branch implements the first "authorable workflows and bidirectional
collaboration" milestone of the agreed roadmap. Its application version is
**3.0.0**. The operator wire major remains **3**; optional SDK **3.6** fields extend
existing v3/v3.5 packages. The scientific library keeps its independent version.
This is development source, not a published or installer-accepted release.

## Working paths

| Area | Implemented behavior | Boundary |
| --- | --- | --- |
| Workflow authoring | Strict `biopipe.workflow` YAML, stable node/edge IDs, branches, route snapshots, JSON values and execution sidecars; CLI init/lint/format/export/prepare/run | Existing execution YAML remains a separate low-level format |
| Desktop YAML | Export a five-file editable YAML project ZIP and import it through the workflow menu | Browser imports resolve input paths against the selected workspace; data is not copied into this project archive |
| Lightweight startup | Start the management service, read registry metadata; registration neither imports provider code nor resolves scientific dependencies | The desktop still needs a small Python management service; this is not a browser-only launcher |
| Validation | Route-scoped, selected-host checks; ready-only cache; explicit dependency preparation; run refuses blocked environments | Existing managed dependency directories and configured SSH installations remain the supported targets |
| Scripts | Drop Python/R/C/C++ source; named file ports; code/parameter views; Python literal extraction; independent execution JSON; explicit promotion into a categorized v3 package | One file output per graph script node; C/C++ needs the selected host's compiler; no invented semantic or streaming behavior |
| Defaults | Imported literal values become initial parameter defaults; existing workflow values win and remain frozen | Parameter extraction is conservative static analysis, not arbitrary program evaluation |
| Native operator source | Inspect the exact registered Python source in the code tab | Read-only; edit an extension source and refresh to publish a new implementation |
| Data contracts | Separate logical type and representation; bounded deterministic conversion plans, visible edge marker, runtime memory/disk checks | Initial automatic conversions cover NumPy array and NPY mapping; matrix-to-list requires an explicit semantic operator |
| Human/agent activity | Durable transaction IDs, compact cursor events, on-demand diffs, visible activity and conditional undo | A later conflicting human edit blocks an old inverse operation; activity is committed changes, not private model reasoning |
| Independent export | Python file-script pipeline, run script, frozen values and supplied relocatable runtime; actual moved-directory execution test | Native scientific operators and unimplemented conversion adapters are rejected instead of omitted |

## Compatibility and execution

All scientific runs still pass through the existing shared task service and
isolated worker. Host resource admission, fixed-order planning, lazy reads,
streaming-capable native operators, disk artifacts and emergency spill remain in
place. A script's own algorithm is not automatically rewritten into streaming
code. Script subprocesses and compilers are owned process trees, with cancellation,
attempt-local temporary files and retained logs.

Ordinary v3 packages keep their IDs and default contract behavior. Saved routes
retain independent parameter JSON; editing an operator's current defaults does
not rewrite these values. Promoting a script creates a new distinct operator ID,
parameter JSON and generated Markdown. Registration is explicit and does not run
the script. Duplicate IDs are rejected by this shortcut rather than silently
replacing an existing implementation.

Read [readiness](readiness.md), [script operators](script_operators_v3.md),
[workflow YAML](workflow_yaml_v3.md), [formats](data_formats.md),
[collaboration](canvas_collaboration.md) and [portable packages](portable_packages_v3.md)
for commands and constraints.

## Acceptance coverage

The focused tests cover static registration, existing headless operations,
schema compatibility, frozen parameter values, real script/provider subprocesses,
managed memory and route compilation, conversion cancellation/quota behavior,
remote readiness RPC, concurrent editing and guarded undo. Desktop authoring tests
exercise the new editor, script drop, promotion, localization and bridge transport.
The public-project round trip is checked through the same HTTP endpoints as the UI.

The standalone test copies a real CPython runtime, moves the output package and
runs it without importing BioPipe. That is evidence for the tested Python file
workflow, not evidence for arbitrary Hi-C/R/C++ portable packages or a clean-machine
installer. A new Setup build and actual double-click acceptance remain release
gates; no GitHub release is created by this implementation task.

Recorded development checks on 2026-11-06 (groups overlap; do not add them into a
single unique-test count):

| Check group | Result |
| --- | --- |
| Full frontend suite | 154 passed; production TypeScript/Vite build passed |
| Studio, imports, isolated-install compatibility, dependencies and new HTTP/worker integration | 43 passed |
| Public workflow YAML, v3 protocol and new script worker integration | 33 passed |
| Readiness and execution planning | 62 passed |
| Actual coordinator and execution API regressions | 15 passed |
| Existing conflict isolation and library package workers | 22 passed |
| Static host-version compatibility without dependency resolution | 3 passed |
| MCP/CLI preparation permissions and installed guides | 15 passed |
| Independent bundled-runtime export | 2 passed |

Computer-control initialization failed before UI inspection, so browser/native
window acceptance was not performed. Component interaction tests and real HTTP/
worker checks do not substitute for the later Setup double-click gate.

## Remaining roadmap milestones

These items remain follow-up work rather than hidden claims of 3.0 support:

- Per-node checkpoints and content-verified cross-run cache, unified scratch/IPC
  garbage collection, native DAG scatter/gather and bounded automatic retries.
- Full native scientific portable adapters, included converter closure and
  clean-target offline Hi-C numerical acceptance.
- A selectable new local interpreter installation path and full environment
  provisioning UI, beyond current managed dependency targets and SSH setup.
- Automatic private dependency target preparation for workflow-local scripts.
  Currently unresolved script dependencies fail readiness; promoting a script to
  a normal v3 package uses the established explicit dependency repair/isolation path.
- Pluggable converter installation, Arrow/Parquet/DuckDB workload adapters and
  remote object stores beyond the first verified representation conversions.
- Slurm/container/Nextflow executors; institutional scheduling and telemetry.

These later items keep separate capability checks and acceptance criteria. They
do not change the existing library or require every desktop user to run a cluster.
