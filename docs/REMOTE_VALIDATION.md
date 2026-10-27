# SSH execution acceptance — 2026-10-27

This records development-source acceptance on Windows and a Linux cloud
container. No Windows desktop archive or GitHub release was rebuilt in this task.
See [REMOTE_EXECUTION.md](REMOTE_EXECUTION.md) for setup and operating instructions.

## Automated checks

| Check | Result |
|---|---|
| Windows Python 3.11 full suite | 448 passed, 5 skipped, 297.72 seconds |
| Final remote/source/container-memory checks, Windows | 15 passed |
| Final remote/source/container-memory checks, Linux Python 3.11 | 14 passed, 1 skipped |
| Frontend TypeScript and Vite production build | Passed |
| Frontend Vitest suite | 55 passed across 10 files |

The final targeted run covers the compressed companion-file correction added
after the full suite started. The Linux skip is the loopback SSH test because
Paramiko is not installed in the compute environment; the server bridge does not
need it. That test passed on Windows with Paramiko 4.0.0, and Windows-to-Linux SSH
was exercised separately against the real gateway. The full-suite skips cover
optional/runtime-specific tests, including the opt-in real Hi-C tool tests;
earlier full Hi-C acceptance is recorded in [HIC_VALIDATION.md](HIC_VALIDATION.md).

Tests cover explicit host-key trust, Unicode and large framed messages, bounded
retries, server path boundaries, offline frozen parameter snapshots, no local
execution fallback, independent parameter JSON, worker survival, failed Reader
logs, duplicate-submission protection and cgroup v1/v2 headroom.

## Actual Windows UI and SSH checks

The production-built frontend was opened on Windows against the source backend.
It connected through the cloud provider's numbered SSH gateway to the existing
Linux Python environment. Only synthetic inputs were used.

1. Connected from the server dialog and read the server catalog: 67 operators.
2. Browsed server files, selected `expression-demo.csv`, and ran the branched
   quality-filter → PCA / streaming-description example from the UI.
3. Verified successful events, launcher output and the full-console link.
4. Submitted a five-step Hi-C graph through the same authenticated desktop API:
   compressed PAIRS → balanced contacts → expected / insulation / window → heatmap.
5. Disconnected SSH while that job was running, then reconnected. The job completed
   and appeared in history; its canvas could be restored in the Windows UI.
6. Submitted an empty CSV as a deliberate Reader failure. The UI displayed the
   error, complete traceback and worker exit status rather than an empty console.
7. Confirmed Linux badges in the catalog and on Hi-C operator cards. Confirmed
   the memory preview used the Linux container, not Windows or the physical host.

The Hi-C job started at **2026-10-26 20:03:43 UTC**. SSH disconnected at
**20:03:45 UTC**; the job finished successfully at **20:04:01 UTC**. Actual
external-tool operations took approximately 6.48 seconds for contact construction,
5.32 seconds for expected values and 5.01 seconds for insulation. The selected
window and heatmap were 20 × 20. The synthetic PAIRS input contained 39,718 contacts.

The server job directory contained `task.yaml`, `parameters.json` (five step
parameter records), `plugins.lock.json`, `job.json`, `console.log` and launcher
events. Contact files, cached arrays, reports and the PNG stayed on the server.
The Windows job directory contained no remote `parameters.json` or remote data
artifacts. Diagnostic metadata, logs and screenshots were retained locally.

## Findings fixed during acceptance

- The numbered gateway needs a blank line after the instance choice. Repeating
  the instance number can accidentally type into the attached shell.
- This gateway exposes container stream envelopes and transforms non-UTF-8 bytes.
  Bulk responses could be corrupted or truncated. The SSH control transport now
  compresses messages, sends bounded ASCII frames, checks each fragment and the
  complete payload, and waits for receipts before continuing. Failed receipts
  have bounded retries; this does not alter operator declarations.
- The container's hard memory limit is **90 GiB**, while the initial host scan
  suggested a budget of **618.7 GiB**. The corrected one-shot scan considers the
  process's cgroup and its visible parent limits, yielding an **80.8 GiB** preview
  at acceptance time. It does not introduce periodic memory replanning.
- Remote Reader selection now respects declared compression support and checks
  companion filenames after removing the compression suffix. A compressed text
  BED cannot be mistaken for PLINK when PLINK companion files are present.

The container accounting implementation follows the Linux kernel's
[cgroup v2 memory interface](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
and [v1 memory controller files](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v1/memory.html).
The gateway envelope diagnosis used the
[Moby stream format](https://github.com/moby/moby/blob/master/client/container_logs.go).

## Limits of this acceptance

This is source/frontend acceptance, not a fresh EXE or clean-server installer
test. The server environment was already prepared. Automatic provisioning,
cluster scheduling, automatic data transfer and remote image previews are outside
this implementation. Passwords and passphrases are held only for the current
editor process; account credentials are not included in the evidence archive.

The final uploaded source/test candidate contained 355 files and had SHA-256
`7ae174c35146cc2903a4cd8c579d01a2096b2c2a23a15e77063039f2cfee85c5`.
Documentation written after acceptance is not included in that test archive.

After all jobs reached terminal states, the client disconnected and discarded
session credentials. The provider accepted the requested shutdown with HTTP 200
and reported `shutdowning`; final power-off was not independently queried.
