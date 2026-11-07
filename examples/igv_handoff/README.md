# Operon → IGV genome-track handoff

This optional SDK package demonstrates the boundary between automated analysis
and a specialist interactive viewer. Operon performs the interval computation;
IGV opens the resulting BED and bedGraph files for inspection. It is not an
embedded IGV browser, a universal visualization adapter, or a Hi-C heatmap tool.

## Install and use the example operator

From the repository root, in the same Python environment as Operon:

```text
python -m operon plugin check examples/igv_handoff
python -m operon plugin build examples/igv_handoff
python -m operon --workspace /path/to/project plugin install examples/igv_handoff/dist/operon_igv_example-0.1.0-py3-none-any.whl
```

Connect `BedReader` → `interval_merge` → `example.genome_tracks`. Supply an
explicit reference `assembly`; retain the final `tracks` output. The operator's
[Markdown guide](operon_igv_example/tracks.GenomeTracks.md) and independent
[parameter schema](operon_igv_example/tracks.parameters.json) describe the input
contract and the meaning of the quantitative track.

This export uses chromosome metadata from the actual Form and named columns;
it does not assume all rows belong to one chromosome. The writer preserves
large exact integer coordinates, validates sorted non-overlapping intervals,
and uses bounded write buffers. Operon still admits the full input and can
spill other cached artifacts. It does not turn `interval_merge` into a
streaming algorithm. No new scientific or GUI dependency is needed by the exporter.

## Public interface and current limits

An authenticated client uses the existing public application API:

```text
GET /api/v1/jobs/{job}/artifacts
GET /api/v1/jobs/{job}/artifacts/{artifact}/preview
GET /api/v1/jobs/{job}/artifacts/{artifact}/file?role=bed
GET /api/v1/jobs/{job}/artifacts/{artifact}/file?role=bedgraph
GET /api/v1/jobs/{job}/artifacts/{artifact}/file?role=provenance
GET /api/v1/jobs/{job}/parameters
```

The first call identifies retained file artifacts; preview lists their roles.
The job and parameter endpoints provide operator generation, frozen parameters
and memory settings. Downloads stream the selected native output. The API does
not expose arbitrary input paths or private pickle metadata. Ordinary Form
artifacts expose numeric NPY data, which alone is insufficient to reconstruct
arbitrary genome coordinates. This example therefore exports from the Form
**inside the worker** and registers ordinary `FileArtifact` roles.

IGV can load accessible files, URLs, and session XML. It does not automatically
inherit Operon's authenticated API token. This example explicitly copies the
selected generated files into a local handoff directory; for a remote job,
network access and secure transfer must be handled by the integrating client.
There is no automatic “Open in IGV” desktop button or remote-IGV controller in
this example. The API does not execute an external viewer on behalf of a client.

## Reproduce the computation and handoff

Use a new empty output path. The acceptance script installs the example into
an isolated profile, starts the ordinary headless service, and submits a real
saved workflow using the public API. No desktop canvas is needed.

```text
python scripts/accept_igv_handoff.py --output .tmp/igv-acceptance
```

The script checks nine input intervals on two synthetic chromosomes against
five analytically expected merged regions, including each region's source
interval count. It verifies native artifact hashes, independent workflow and
job parameter JSON, execution settings, and enabled memory admission. It leaves
`evidence.json`, the full job record and logs, plus a `handoff/` directory with:

- `merged.bed`, `values.bedgraph`, and `provenance.json` copied from the job's
  native file artifacts through the authenticated API.
- `synthetic.fa` and its exact `.fai` index for two 3,000-base chromosomes.
- `session.xml`, using relative references so the whole directory is movable.
- A local batch script that opens the session, visits both chromosomes and
  requests snapshots. Its absolute launch paths must be regenerated if moved.

The synthetic genome is a format/control-flow fixture, not a biological dataset.
The bedGraph value is the **number of source intervals per merged region**, not
base-level read coverage. BED and bedGraph retain zero-based, half-open
coordinates; IGV's locus navigation displays one-based positions. No coordinate
shift is applied to the files. See the [UCSC bedGraph specification](https://genome.ucsc.edu/goldenPath/help/bedgraph.html).

## Open the same files in IGV

Download a desktop build from the [official IGV download page](https://igv.org/doc/desktop/DownloadPage/).
The tested portable all-platform distribution is IGV 2.19.8; it requires Java
21 or newer. No installer or global preference changes are required.

On Windows, the following parameterized launcher opens a visible IGV window
with a 1 GiB Java heap and task-local settings. Replace the four paths with
the paths on that computer; no developer-machine path is embedded in the code.

```powershell
./scripts/open_igv_handoff.ps1 -IgvDirectory tools/IGV_2.19.8 `
  -JavaExecutable tools/jdk-21/bin/java.exe `
  -HandoffDirectory .tmp/igv-acceptance/handoff `
  -SettingsDirectory .tmp/igv-acceptance/igv-settings
```

Alternatively, use IGV's **File → Open Session** and choose `session.xml`.
Inspect both chromosomes and the two tracks. Computation success in
`evidence.json` is distinct from visual acceptance; the script leaves visual
status pending until a person/desktop test actually verifies IGV's display.

The interface is based on IGV's documented [session format](https://igv.org/doc/desktop/UserGuide/sessions/),
[custom references](https://igv.org/doc/desktop/UserGuide/reference_genome/),
[batch commands](https://igv.org/doc/desktop/UserGuide/tools/batch/), and
[command-line flags](https://igv.org/doc/desktop/UserGuide/advanced/command_line/).
Sessions reference external files; they do not embed the data.

## Focused regression tests

```text
python -m pytest tests/test_igv_handoff_example.py -q
```

These cover two-chromosome identity, exact coordinates above 2^24, named values,
hashes, refusal of absent chromosome metadata, invalid/fractional/overlapping
intervals, and cancellation without registered partial output. The acceptance
script additionally exercises installation, the worker, the scheduler, immutable
parameters and the native-file API. Neither replaces IGV visual verification.
