# Hi-C workflows

BioPipe Studio v0.6.1 adds three operators and four file Readers. It reuses
`sequence_stats` for FASTQ quality summaries, `select` for bounded contact-map
windows, and the existing plotting, filtering and annotation operators for their
outputs. Both full and Lite desktop archives include these additions. The full
Windows archive includes the desktop runtime; Linux external tools are prepared
separately in the execution environment described below.

## Routes and data

| Entry | Route | Required auxiliary files |
| --- | --- | --- |
| Paired FASTQ, optionally gzip/bzip2/xz | `routes/hic_fastq/task.yaml` | R2, reference FASTA, chromosome sizes |
| BAM or SAM | `routes/hic_bam/task.yaml` | Matching chromosome sizes |
| pairs, optionally gzip/bzip2/xz | `routes/hic_pairs/task.yaml` | Matching chromosome sizes |
| Existing cool/mcool | Cooler Reader → select/analyze_contacts | Explicit resolution for mcool |

Each route has a separate **parameters.json** containing its concrete values.
Edit that file and source locations to use a template. Registry maintenance reads
both files, validates the route, and records both hashes. Saving/importing a graph
continues to use the v3 frozen parameter snapshot; later schema-default changes do
not change a saved workflow.

Scientific helpers live alongside the Reader/Step implementations, inside the
existing v3 code-fingerprint boundary. Changes to parsing, contact selection or
analysis adapters therefore change code identity; parameter JSON remains part of
the declaration identity. Discovery still reads declarations without executing
the scientific helpers or launching external tools.

The example `chr1:0-1000000` window must be replaced with a region that exists in
the chosen assembly. Template data are placeholders, not bundled genomes. The
pairs template explicitly sets `min_mapq=0` for already-filtered contacts. Raise it
when input declares `mapq1` and `mapq2`; otherwise a nonzero threshold is rejected.

## Minimal operator set

* `sequence_stats(fastq_summary=true)` streams both mates together and reports
  reads, bases, length, GC, N fraction, mean Phred, Q20 and Q30 per mate. Pair IDs,
  read counts and sequence/quality lengths must agree. This is a QC summary, not
  adapter trimming or a replacement for a library-specific QC protocol.
* `align_reads` validates paired FASTQ, runs BWA-MEM with explicit `-5SP` settings,
  and writes BAM with samtools. Reference indices are generated in the run's
  private output directory; the original FASTA is never indexed in place.
* `build_contacts` name-sorts BAM/SAM, parses alignments with pairtools, filters
  declared pair types/MAPQ, sorts, deduplicates, and bins contacts with cooler.
  Input pairs bypass alignment parsing. The output retains raw counts, filtered
  pairs, duplicate statistics, optional balancing weights and provenance.
* `analyze_contacts(method=...)` calls cooltools for `expected`, `compartments`,
  `insulation`, `loops`, or `pileup`. Analysis tables become ordinary Forms;
  pileups become small matrix Forms. Reuse existing plots and table operators.
* `select(source_type=contact_matrix)` reads only a requested cooler rectangle.
  `region` and optional `region2` are **0-based, half-open** chromosome intervals.
  Use `balanced=false` to view counts. Use existing `heatmap`, with `dim=bin1`,
  `other_dim=bin2`, `select=all` and both clustering options false, to retain genome
  order rather than clustering contact-map bins.

The pairs format is **1-based**. The adapter reads `#columns`, validates positions,
and supplies cooler's 1-based ingestion mode; do not pre-subtract one. Only mapped
`UU` contacts are retained by default. Paired alignments retain supplementary
records; the default walks policy is `5unique` and is configurable. These choices
must match the experiment. Automatic restriction-fragment assignment, adapter
trimming, biological replicate merging, differential Hi-C and GPU algorithms are
not implemented by this initial route.

Balancing is ICE through cooler, with convergence failure reported as a failed
step. This is separate from BioPipe's generic numeric `normalize` operator.
Optional mcool output currently contains raw aggregated resolutions; the primary
base-resolution cool retains the requested balancing weights. Balance other
resolutions before weighted downstream analysis.

Compartment vectors without `phasing_track` are explicitly **unoriented**: their
sign is not an A/B assignment. A phasing track is a BEDGraph-like file aligned to
the same assembly. Insulation windows must be multiples of the resolution. Loops
are cooltools dot calls, not arbitrary peaks or evidence of a molecular mechanism.

Loops and pileup can accept the `expected` output as a second input. Its original
TSV and provenance are used, rather than a displayed/selected subset of its Form.
The matrix identity, resolution, weight, view and ignored diagonals must match.
Otherwise the adapter rejects the connection at run time. Without that input,
the operator computes a matching expected table itself.

## Linux tool environment

The raw-read tool chain is a Linux workload. The Windows bundled Python remains
usable for editing, FASTQ QC and local Cooler region previews, but does not bundle
BWA, samtools, pairtools or cooltools. They are external executables, not ordinary
operator Python dependencies; each run performs tool/version preflight before
calling them. BioPipe does not install WSL, change the host OS or run pip during
registry discovery.

Create an isolated environment, then install this checkout:

```bash
conda create -y -p ./hic-env --override-channels -c conda-forge -c bioconda \
  python=3.11 bwa=0.7.19 samtools=1.22.1 pip
conda activate ./hic-env
python -m pip install -e . pytest -r requirements-hic-linux.txt
python -m biopipe registry check
BIOPIPE_HIC_REAL=1 python -m pytest tests/test_hic_real.py -v
```

For a real CLI job, copy one route directory, set the source paths in `task.yaml`
and the concrete values in its `parameters.json`, then run the directory:

```bash
cp -R routes/hic_pairs work-hic
# Put inputs under work-hic/input, or configure absolute server-local paths.
# Replace the example genomic window and choose appropriate resolution/filters.
python scripts/run.py work-hic
```

Outputs and logs are written under `work-hic/output`. FASTQ/BAM templates use the
same entry point. Check available RAM and disk before applying a template to a
whole genome; the example 2 GiB operator workspace is a starting configuration,
not a claim that every genome or resolution fits it.

The Hi-C environment pins pandas 2.2.3 because cooltools 0.7.1 dot clustering
depends on behavior changed in pandas 3. This constraint belongs to the external
tool environment and does not constrain unrelated desktop operators.

Set `executor=native` on Linux. On Windows, `executor=auto` chooses WSL;
`wsl_distribution` optionally selects an installed distribution. `tool_paths`
overrides executable paths in that execution environment. WSL needs `python3`
for the process-group relay. A missing environment/tool produces an actionable
error and retained logs. WSL's adapter must be tested on the user's installed
distribution; Linux acceptance does not certify WSL itself.

File parameters marked `x-biopipe-path: workflow` resolve relative to the
workflow directory. Reader parameters marked `source` resolve beside the main
input (R2 beside R1). Studio resolves and freezes those paths when preparing a
job, and exports relative paths again. The Studio project boundary still applies;
use a project directory containing the data. CLI tasks can use absolute paths.
No account name, server address or developer-machine directory is stored in the
operators, registry or templates.

## Memory, streaming and logs

Large FASTQ/BAM/pairs/cool files use the SDK's **FileArtifact**, not a dense Form.
Its in-memory cost is its descriptor. Cache spill/restore and dependency-process
transport serialize the descriptor without copying the payload. Evicting a cache
entry never deletes the referenced input. File size and modification-time checks
detect replacement; these are freshness checks, not cryptographic content hashes.

The existing run-start memory snapshot and active Form cache planner are retained.
`memory_mb` is an admitted external workspace, not a fresh scan of available RAM.
It determines sort/chunk/tile/snippet budgets. Ordinary unpinned Forms can still
spill during these operations. External process memory cannot itself be spilled;
sampled process-group limits stop an oversized command with its logs intact.
Sampling is not a hard OS memory guarantee and brief peaks can exceed the budget.

Dense compartment analysis has a conservative region-size admission check: use
coarser bins, smaller views or more workspace when refused. Pileup batches feature
snippets and combines them with per-pixel valid counts, preserving a mean in the
presence of missing pixels. It does not concatenate all snippets into RAM.
Contact windows allocate only their admitted rectangle and read sparse pixels in
bounded blocks. TSV/NPZ conversion checks output expansion before allocating.

Each external call records argv, executor, elapsed time and exit code in the
existing run log. Full stdout/stderr, tool-version probes, JSON provenance and
outputs remain under that job's `output/artifacts/hic/` directory on failure.
Timeout/cancellation terminates the owned process group. Temporary disk usage is
checked during commands. Large intermediate files require adequate free disk;
file-backed processing does not mean zero disk cost.

## Remote editing boundary

The development editor supports [SSH remote execution](REMOTE_EXECUTION.md):
choose a prepared Linux server, browse its inputs, submit a workflow and view
reconnectable logs. Computation and data remain on the server. Hi-C tool adapters
are marked Linux in the catalog and canvas. The transport uses SSH and a private
Unix socket; do not expose Studio's local HTTP API to an untrusted network.

## Validation and upstream references

`tests/test_hic_workflow.py` covers streaming QC, malformed/mismatched mates,
coordinate conventions, symmetric rectangles, weights, budget refusal and real
child-process logging/cancellation. `tests/test_file_artifacts.py` covers cache and
IPC lifetime. `tests/test_hic_real.py` requires the actual Linux tools and generates
its own genome, paired reads and contacts; it verifies counts, balancing, analysis
outputs and the existing heatmap integration. Fake executables are not scientific
acceptance evidence. See `HIC_VALIDATION.md` for the latest recorded results.

Primary tool documentation: [pairtools pipeline](https://pairtools.readthedocs.io/en/latest/protocols_pipelines.html),
[Cooler schema](https://cooler.readthedocs.io/en/latest/schema.html),
[cooltools CLI](https://cooltools.readthedocs.io/en/latest/notebooks/command_line_interface.html).
