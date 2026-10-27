# Automatic deployment and startup validation

Validated on 2026-10-27 using Windows x64 and an authorized Linux x86_64 server.
All analysis inputs were synthetic. Credentials and user datasets are excluded
from the release and this report.

## Startup and migration

The reported startup failure was reproduced with an older built-in registry.
Migration also encountered unfinished survival-analysis drafts. The fix was
validated with the existing profile and by double-clicking the full Windows EXE.
The editor loaded the existing canvases and route library using its bundled Python.

Regression tests verify recoverable original bytes, a single migration, untouched
historical jobs, editable missing draft parameters, strict execution requirements
and rejection of incompatible external providers without partial changes.

## Actual Linux deployment

A new managed prefix was prepared through SSH without supplying a Python path.
The bootstrap created its own Python 3.11 environment and installed native tools.
The server's unrelated system Python was not used or modified. Download caches
were reused for later candidates; the timings below are not cold-network benchmarks.

The final implementation candidate connected in 233.89 seconds. A second connection
took 36.33 seconds without reuploading source or reinstalling dependencies. All
86 bundled dependency probes and BWA, samtools, pairtools, cooler and cooltools
executable checks passed. Direct dependency `psutil` and transitive dependency
`certifi` were deliberately removed from the task-owned environment; reconnecting
from the running desktop repaired both in 37.48 seconds and passed the checks again.

The installed scientific stack included pairtools 1.1.2, cooler 0.10.4,
cooltools 0.7.1, NumPy 2.4.6 and pandas 2.2.3. One pip resolution handles the Python
libraries; micromamba supplies Python, native tools and compilers. This avoids
replacing NumPy underneath prebuilt Conda scientific extensions.

## Hi-C execution and persistence

Two real-tool Linux tests passed:

1. Paired FASTQ quality control, BWA alignment, BAM pairing and contact-map creation.
2. Compressed pairs, balanced contacts, expected values, compartments, insulation,
   loops/pileup and an existing heatmap operator.

The Windows desktop then submitted a separate five-operator route: contact-map
construction, expected values, insulation, region selection and heatmap. It completed
with exit code zero and retained a nonempty console log. Its server job contained
`task.yaml`, `parameters.json`, `plugins.lock.json`, `job.json`, `console.log` and
launcher events. Memory planning and automatic spilling were enabled. No matching
local directory containing job inputs, parameters or results was created.

## Test boundary

The full implementation regression completed with 465 Python tests passing and
five platform/opt-in skips. The final remote/startup group passed 22 tests after
adding transitive dependency repair. Frontend tests passed 57 cases. Actual Windows
host lifecycle checks covered WebView2 startup, single-instance behavior, occupied
port fallback, worker cleanup, history recovery, draft flush and graceful shutdown.

These server measurements used the final implementation commit `0fa5b06` before
release-version and packaging-documentation updates. The v0.6.2 release attachment
`VERIFICATION.md` records checks against the final Lite/full archives. The server
was sent its authorized shutdown request after evidence collection.

Automatic deployment is currently limited to Linux x86_64. It needs network access
and writable storage, retains older environments for historical runs, and does not
switch an actively served workspace to another source revision. Cancellation stops
the client wait; an outstanding installer may finish before releasing its lock.
