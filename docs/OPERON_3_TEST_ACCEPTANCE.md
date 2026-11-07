# Operon 3.0.0 Setup acceptance

## RC8 compatibility follow-up

RC8 adds verified official v2.6.0 bundled compatibility receipts and fixes the
release recorder's split-library source lookup. Use a fresh installation/profile
and the original archived v2.6.0 acceptance ZIP. Import, prepare and run it after
explicit dependency preparation; compare the frozen parameter and memory values,
check the new job's compatibility receipt, and retain the unchanged old ZIP. No
manual repin or old profile copy is allowed. Reopen from the shortcut, repeat the
run/CLI checks and verify clean exit and old-profile isolation. RC7 UI evidence
may be retained for unchanged features; identify each candidate in the report.

## RC2 management-runtime changes

### RC4 follow-up gates

RC4 retains the management-runtime boundary below. Transfer the **complete test
ZIP**, extract it, and verify that `FORWARD_TO_TESTER.txt`, `SHA256SUMS.txt`, the
Setup EXE and the script fixtures are present. Use the new hash, not RC3's hash.

- On an unsaved blank canvas, drop at least six scripts, select all and delete,
  then drop again. Repeat at least five times using the central empty-state
  illustration, its input button, and ordinary grid as drop targets. Repeat
  around saving, switching/closing/reopening tabs, and restarting via the
  shortcut. Each file must add exactly one node. Measure elapsed time and count
  successes. Use real Explorer dragging: synthetic DOM events are a separate
  developer regression test, not this OS/WebView acceptance gate.
- Open a new canvas immediately after startup, then rapidly create/switch tabs.
  No `Presence references an unknown document` message may appear. After sync,
  Agent context must refer to the current tab and selection, and drafts must
  remain intact. This covers registration/presence ordering during connection
  and event polling, not just an idle-server click.
- In a **fresh profile**, time first and unchanged repeat refreshes. Untouched
  factory sources must reuse the registry without rebuilding, installing or
  precompiling every provider. Then add a synthetic operator with a unique ID
  and refresh: actual edits must still be discovered and validated. Do not use
  an already detached RC3 library as the first-refresh timing sample.

- Save a script as a reusable operator while an unrelated library search is
  active and its category is collapsed. The sidebar must reveal the new ID
  immediately, without refresh. Clear the search and confirm it remains in its
  chosen category. Wait through a background poll and repeat after reopening.
- Import `.py` files from Explorer repeatedly and record end-to-end elapsed
  times and success counts. A file drag uses copy semantics and shows a pending
  import indicator. Invalid Python must produce an error with no partial nodes.
  This check requires actual OS dragging; API timings do not replace it.
- Time the first library refresh separately from an unchanged repeat refresh.
  First-time editable source preparation can still take longer. During refresh,
  try editing a node and inspect a script; record responsiveness.
- Verify that idle background polling does not continually download the full
  unchanged catalog. A changed generation must still become visible, including
  a library update performed by another application client.
- The RC3 evidence still left old v3/v3.5 import, actual PNG/PDF/SVG link display,
  node-body dragging, Ctrl multiselection, two-node copy/undo and SDK 3.6 conversion UI and
  real execution untested. Complete them where fixtures are available, otherwise
  keep them explicitly NOT TESTED. Do not infer them from backend tests.

The startup label now says "starting the workbench service". A lightweight Python
management process still starts with the application; this is not Python-free
desktop startup. No scientific dependencies are installed during idle startup.

RC2 replaces the previous all-analysis bundle with a management runtime. Confirm
the package manifest says `runtime_mode: management`. Pandas, SciPy, Matplotlib,
PyTorch and specialized scientific packages must be absent from its site-packages
before **and after** analysis dependency preparation. NumPy is intentionally kept
for Form, memory handling and bounded previews. First-time scientific preparation
needs networking; missing dependencies at initial Validate are expected.

For the Agent backend phase below, pass `--prepare-environment` explicitly. This
authorizes only the synthetic route's preparation and does not grant installation
permission to ordinary run calls. For the optional isolated backend diagnostic,
add `--prepare-analysis` to verify a real PCA/plot workflow, CLI/MCP permissions
and the management-runtime boundary as well as standard-library script branches.
Record that online preparation separately from GUI installation.

This guide verifies a **candidate**, not a published release. Run it on the
Windows test machine using the delivered Setup and its checksum manifest. Record
PASS, FAIL or NOT TESTED for every item. A failed or skipped gate must remain
visible in the final report. Do not publish, disable dependency checks to obtain a
pass, or substitute a source checkout for the installed application.

Related instructions: [packaged Agent acceptance](../scripts/verify_release_agent.md),
[3.0 scope](V3_IMPLEMENTATION.md), [naming compatibility](rebranding.md),
[YAML](workflow_yaml_v3.md), [scripts](script_operators_v3.md), and
[readiness](readiness.md).

## 1. Package identity and preservation baseline

Use a new evidence directory, for example `Documents/Operon-acceptance/3.0.0-<candidate>`.
The example is a test location, not an application requirement. Record Windows
version/architecture, candidate filename, size, SHA256 and the supplied manifest
entry. Compare the **actual EXE hash**, not just the name or version displayed by
its parent directory:

```powershell
Get-FileHash -LiteralPath '<received-package>/Operon_Setup.exe' -Algorithm SHA256
```

Before installation, record existence and hashes of the old global runtime hint,
old Operon installation receipt/uninstall registration, existing shortcuts, and
the previously agreed sample of old profile/provider files. If a file is absent,
record absence. Do not delete, repair, migrate or rewrite the old profile. Keep
old evidence and user data unchanged. Do not install a system Python for this test.

Copy `examples/workflows/script_pipeline/` from the delivered acceptance material
into a new test directory. It contains only synthetic CSV generation and scaling
code. No public dataset, model download or SSH server is needed for the mandatory
Windows checks. If a referenced fixture is missing from the delivery, report the
missing fixture; do not silently use files from an unrelated build.

## 2. Actual installation, branding and startup

1. In Explorer, **double-click `Operon_Setup.exe`**. Record the installation UI,
   chosen destination, start/end times, installer result and log locations.
2. Launch the installed program using the installer's normal launch action or
   its newly created shortcut. Record the actual EXE path. Confirm **Operon** in
   the window/shortcut and application version **3.0.0**. Check the icon in the
   newly installed build, not an old cached Operon shortcut.
3. From the installation receipt and startup log, record the installation ID,
   profile/workspace path and selected Python path. The interpreter must belong
   to this installation. The profile must be new; an old v1 registry must not
   block startup or be migrated automatically.
4. Leave the initial workspace idle. Record the initial task count. Inspect
   startup/dependency logs and child processes: opening the application and
   reading the library must not start pip/conda/R scientific-package installation
   or execute analysis nodes. Loading the management backend and checking bundled
   runtime integrity are expected and are not scientific execution.
5. Confirm that existing Operon shortcuts/registration and the sampled old
   profile/runtime files retain their baseline identity. Report any intentional
   installer coexistence policy separately; do not hide unexpected rewrites.

Do not use `--quiet`, a Python server command, a simulated browser session or a
direct backend launch as evidence for these steps. Keep the actual installed
window open for the Agent phases below.

### Optional packaged-backend diagnostic

The installed package also contains `scripts/verify_operon_candidate.py`. Run it
with **that installation's bundled Python**, using new evidence paths **outside
the installation**. The work directory must not already exist; the report file
must not exist either:

```powershell
& '<installed-package-root>/runtime/python/python.exe' -I `
  '<installed-package-root>/scripts/verify_operon_candidate.py' `
  --version 3.0.0 `
  --report '<new-evidence>/candidate.json' `
  --work-dir '<new-evidence>/candidate-work'
```

Do **not** pass `--allow-development` for package acceptance. The verifier checks
the packaged interpreter/EXE, then uses a temporary home and isolated synthetic
profile under its new work directory. It can run against an installed package
without reusing or changing the desktop's real profile or installation identity.
It tests the packaged API, literal extraction, frozen values, YAML round-trip, an
actual branched worker, memory/parameter artifacts and backend shutdown. Preserve
the report and work directory, including failures.

This helper uses its own small fixture: four generated values, scaling factors
5 and 7. Those expectations differ intentionally from the five-row, ×3/×2 manual
fixture below. Its success is **packaged backend evidence only**. It does not
replace actual double-click Setup, shortcut launches, visible interactions or the
six real-desktop Agent phases.

## 3. Six Agent phases on the real installed instance

Use the installed bundled Python and the package root containing `operon`, `src`
and `scripts`. Obtain the live workspace path from the startup log. Run the
following from that package root to list instances; select the actual desktop
instance, not a leftover headless service:

```powershell
& '<bundled-python>' -m operon --workspace '<workspace>' service status
```

Record the non-secret instance ID. Never include discovery secrets, tokens or
credentials in the report. Set paths explicitly in a test PowerShell window:

```powershell
$testPython = '<bundled-python>'
$testCode = '<installed-package-root>'
$testWorkspace = '<fresh-profile-workspace>'
$testInstance = '<live-desktop-instance-id>'
$testEvidence = '<new-evidence-directory>/agent'
$testVerifier = Join-Path $testCode 'scripts/verify_release_agent.py'
$testArgs = @('--code-root', $testCode, '--python', $testPython,
              '--workspace', $testWorkspace, '--instance', $testInstance,
              '--evidence', $testEvidence, '--version', '3.0.0')
& $testPython $testVerifier backend @testArgs --prepare-environment
```

Always pass `--version 3.0.0` explicitly. Do not
pass `--allow-headless`. Then perform the phases with the same arguments:

| Phase | Required observation |
| --- | --- |
| `backend` | Real CLI/MCP permission checks, synthetic CSV/PCA/statistics/scatter task, frozen values, logs, original artifact files and durable submission receipt pass. The statistics mean is 7.5; figure size is 90 × 75 mm. |
| `open` | A new synthetic tab appears in the already running desktop. |
| `capture` | First click PCA in the actual EXE. MCP reads that real selection; never publish a fabricated selection through a test API. |
| `apply` | Observe the Agent diagnostic branch, changed tab title and PCA component count 3. Activity displays the committed changes; expand a diff and locate an affected node. The task count must not increase merely because of editing. |
| `undo` | One undo removes that batch and restores the prior graph/parameters. Preserve unrelated subsequent edits; an overlapping edit must produce a conflict rather than overwrite human work. |
| `retry` | After normal close and actual shortcut reopen, select the new desktop instance ID, update `--instance`, and reuse the same evidence directory. The original job is reused; no duplicate task is created. |

For example, `& $testPython $testVerifier open @testArgs`. The six phases are
`backend`, `open`, `capture`, `apply`, `undo`, `retry`; the physical click, UI
observations and restart between them are part of acceptance. Backend JSON alone
does not prove those interactions. In Studio, also open the original PNG, PDF and
SVG result links and record the rendering outcome separately.

## 4. Old workflows, settings and editing

Import a **previously saved synthetic v3/v3.5 workflow** or route bundle from an
earlier acceptance, without changing the original file. Verify node identities,
connections, parameter values and memory settings. Save it as a new workflow in
the fresh Operon profile. If no actual older fixture is available, mark this
compatibility item NOT TESTED; exporting/importing only a new 3.0 graph is a
different test.

Check one-click selection, double-click inspection, node-body dragging,
Ctrl+click multiselection, and Ctrl+C/V of two connected nodes. Verify pasted
internal edges and undo behavior. Grant an expected clipboard permission prompt
only through the tester's normal approval action; a displayed prompt is not a
successful paste. Confirm empty-canvas double-click fits the canvas and idle time
does not unexpectedly fit it.

Set English/dark appearance and a harmless default viewer choice such as
`.hic → Juicebox`. Reopen Settings and later restart to verify persistence in the
new profile's configuration. Switching Settings sections must preserve an
unsubmitted server draft. A saved viewer preference is not proof that an
uninstalled third-party application launches.

## 5. Script drop, literal parameters and library promotion

Use a separate canvas and the delivered `generate.py` and `scale.py` fixtures:

1. Drag both files onto the canvas. A static script node appears for each; no task
   starts. Connect the generator's CSV file output to the scaler's file input.
   Duplicate the scaler to create two branches.
2. For each scaler branch, double-click it, inspect Code, then select **Save and inspect code**.
   Select `factor` and **Extract to parameter JSON**. The imported default must
   be **2**, not an invented value or an unrelated library default.
3. In Parameters, set branch A to 3 and branch B to 2. Rename the nodes and save
   the workflow. Observe independent values for the two instances. The generator
   produces `1,2,3,4,5`; expected branch outputs are `3,6,9,12,15` and
   `2,4,6,8,10`. Validate first, then click Run explicitly and check the actual CSV
   files through result links.
4. Reopen the saved workflow and confirm the values. In an exported **copy**, an
   agent may change only the script snapshot schema's `factor.default` to 99 while
   retaining branch A's explicit value 3. Reimport and validate: the explicit
   frozen value must remain 3. Do not change source/code hashes or the original
   saved files to simulate this check.
5. On the scaler, expand **Save to operator library**, choose a category and a
   unique test ID such as `acceptance.scale3`, then save. Check its title/category
   in the library immediately. This action must not install scientific packages
   or launch a task. Drag the promoted operator onto another branch, validate and
   run explicitly. Check its generated parameter JSON and Markdown exist using
   the normal library/source/documentation interfaces.

The inspector's installed native-source view is read-only. Do not edit immutable
installed packages to test defaults. Script graph nodes currently support exactly
one file output; multiple outputs must be rejected clearly, not silently lost.

## 6. YAML round-trip and format safety

Export the branched script workflow using **editable YAML project**, then import
that project into a new tab. Confirm topology, both factor values, node IDs,
memory/execution settings and pins. The separate JSON values/execution documents
must still be present. This is distinct from the older low-level execution YAML.

With a copy of the delivered standalone script example, run static CLI checks:

```powershell
& $testPython -m operon workflow lint '<fixture-copy>/workflow.yaml'
& $testPython -m operon workflow format '<fixture-copy>/workflow.yaml' --check
```

Lint/format may inspect metadata but must not start an application service or
install dependencies. For the new alias, verify `operon help` if the installer
provides it; the compatibility command `python -m operon help` must still work.

For a UI negative case, duplicate `scale.py` and change only its declared input
from `file.csv` to `file.tsv`. Connect it to the CSV generator. Validation must
report incompatibility and Run must not submit a scientific task. The application
must not silently reinterpret CSV as TSV. Restore the original compatible branch.

For the logical-type rule, execute the following component diagnostic with the
installed Python from the installed package root, recording stdout and exit code:

```python
from operon.conversions import plan_conversion
matrix = {"logical_type": "matrix", "representations": ["numpy.ndarray"]}
vector = {"logical_type": "list", "representations": ["numpy.ndarray"]}
mapped = {"logical_type": "matrix", "representations": ["npy.memmap"]}
assert plan_conversion(matrix, vector)["status"] == "incompatible"
assert plan_conversion(matrix, matrix)["conversion_plan"]["converters"] == []
assert plan_conversion(matrix, mapped)["conversion_plan"]["converters"][0]["id"] == "matrix.npy.write"
print("logical mismatch rejected; direct edge unchanged; verified NPY plan available")
```

This diagnostic verifies the installed planner, not a rendered conversion badge
or a managed conversion run. Those require nodes explicitly declaring SDK 3.6
format capabilities; ordinary legacy nodes do not acquire them by inference.
Report those additional checks as NOT TESTED if no such UI fixture was supplied.

## 7. Readiness, explicit preparation and no surprise execution

Before and after code/parameter/selection changes, observe task count and readiness.
Selection/layout changes should not launch work. An execution-relevant edit
requires revalidation; Run may perform read-only validation automatically but
must not install missing packages or start a blocked graph.

Make a disposable copy of the Python generator with a PEP 723 block declaring
`dependencies = ["numpy==0.0.0"]`. Import it as a script and Validate. Record the
dependency mismatch, unchanged task count and absence of pip activity. Do **not**
try to install that deliberately invalid version. Remove the negative node,
validate the standard-library branch and then run explicitly.

For an ordinary registered operator that truly lacks a supported dependency,
preparation is an explicit action under run permission. Record the request and
installation log if this separate positive test is performed. A missing optional
dependency is not a reason to label the entire library tested or ready. Unresolved
workflow-local script conflicts currently require a prepared environment or
promotion to a standard v3 package using its existing repair/isolation path.

## 8. Restart, reinstall, uninstall and evidence

Close via the normal window control. Record time from the close request to host
and backend termination, backend exit code, remaining owned processes and any
shutdown/log errors. A forced kill or cleanup timeout does not count as normal
exit. Reopen using the actual desktop shortcut, complete Agent `retry`, and verify
saved workflows, registrations and settings. Repeat normal close measurement.

Double-click the same Setup again. Record the new installation/profile identities
and verify the new workspace starts empty. The previous test profile and its
saved output hashes must remain unchanged. Launch and close the reinstalled build.
Uninstall **only this test Operon installation** through Windows Installed apps.
Verify its registration/shortcuts are removed, profiles/results are retained and
old Operon registration/runtime/provider samples match the baseline. List
retained unknown/compiled/cache files; do not delete them to conceal retention.

Deliver a report containing:

- Setup identity/hash; installation paths, selected Python and actual profiles;
- per-section PASS/FAIL/NOT TESTED and exact reproduction for failures;
- three startup/exit observations: initial, shortcut reopen and reinstall;
- Agent phase JSON, task IDs/counts, UI screenshots and original artifact checks;
- workflow/YAML/script fixture copies, frozen values and numerical outputs;
- installer, desktop, dependency and task logs for this test only;
- baseline comparison and preserved-file/leftover summary;
- SHA256 of the evidence archive, and an explicit **not published** statement.

Do not include credentials, discovery secrets, unrelated documents or user datasets.
Windows synthetic acceptance does not validate Linux deployment, Hi-C scientific
correctness, arbitrary R/C/C++ toolchains, all library operators or universal
standalone export. Keep those scopes separate.
