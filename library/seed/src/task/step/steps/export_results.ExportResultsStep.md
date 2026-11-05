# Export results

## Purpose

`export_results` saves an intermediate or final result as ordinary files. Add it
as a branch from any compatible data node; connect further calculations to that
same data node. Exporting does not consume or modify the upstream data. The output
port contains a `FileArtifact`, not a replacement numeric Form.

## Inputs and outputs

Accepts one Form or FileArtifact. Outputs a FileArtifact with file paths, formats,
sizes and the roles reused without copying. Files live in the task output folder
and appear in the existing results viewer, CLI and artifact API. They remain on
the execution host: a remote task saves files on the server.

## Parameter guidance

The adjacent JSON is the authoritative parameter schema. Saved workflows keep
their own values independently of these defaults.

| Format | Behavior |
| --- | --- |
| `auto` | Reuse files from the immediate producer when available; otherwise write a two-dimensional Form as CSV or another tensor as NPY. |
| `native` | Export every original file; fail if none is available. FileArtifact inputs may contain any native format. |
| `csv`, `tsv` | Reuse matching originals, or serialize a two-dimensional Form row by row. |
| `npy` | Reuse matching originals, or write the array with its dtype and shape in bounded buffers; object arrays are rejected. |
| `fasta` | Reuse original FASTA, or serialize `info.sequences` aligned with the first axis. |
| `pdb`, `cif` | Reuse original PDB/mmCIF files only. Never reconstruct a structure from an incomplete numeric table. |
| `hic`, `cool` | Reuse originals or write raw counts from a qualified Form/Cooler in bounded batches. |
| `genbank` | Preserve original annotated records or write DNA sequences with explicit topology. |
| `bed`, `bedgraph` | Write first-axis genomic intervals; bedGraph also exports one numeric column. |
| `graphml` | Write a declared adjacency matrix with node labels and edge weights. |
| `newick` | Write an existing tree in metadata; does not infer a tree from distances. |

Leave `filename` empty for zero-copy reuse of same-task originals. A custom
filename stem creates a separately named copy; multiple files keep their original
names under that prefix so index siblings stay paired. Compression suffixes are
preserved. Duplicate basenames receive a disambiguating number.
External FileArtifact files are copied into the task output so existing
desktop and API file links remain usable. Original inputs are never moved.

`include_labels` controls headers and row labels of **converted** CSV/TSV only.
Native files are byte-for-byte copies or references. NPY is a raw array and does
not serialize Form labels, info or axis_info. `buffer_mb` controls the NPY write
buffer, not the pipeline's memory budget.

## Native file attribution

ProteinMPNN preserves its original FASTA and a score CSV; RFdiffusion preserves
its original PDB files before temporary directories are removed. Their Form
outputs still support downstream calculations. Directly connect an export branch
to these producers to obtain original files. A later transform must not silently
export an ancestor's unmodified native result.

Form-to-native attribution is local to one task and its immediate producer's
report. Export in that task, then carry the resulting FileArtifact across tasks
or execution stages. A restored Form alone is insufficient to locate its original
files; `native` fails with an actionable message in that situation.

## FASTA interpretation

Converted FASTA uses first-axis labels as record names. Sequence count must match
that axis; axis_info, when present, must assign sequences to it. ProteinMPNN now
declares sequences and headers as design-axis metadata, so subsetting keeps them
aligned. A slash-separated multichain sequence becomes separate records named
`design|chain=1`, `design|chain=2`, etc. Reused native FASTA retains the tool's
original headers, reference records and chain encoding.

## Memory and limitations

This is a full-mode operator under the existing admission, cache and emergency
spill policies. It does not claim the report-only streaming protocol. FileArtifact
inputs are metadata references; NPY conversion writes bounded chunks and tables
write one row at a time. The planner must still admit the input Form and metadata.
No extra whole-array concatenation is performed. CSV/TSV rejects tensors with
other than two dimensions instead of silently flattening them.

## Contact maps and Juicebox

For a sparse full map, connect the original `.cool` FileArtifact with `format: hic`.
A `.mcool` source also requires `resolution`. Pixel blocks are read directly; no
dense genome-wide matrix is created. Rebin explicitly before changing resolution.

A Form must be a square symmetric raw-count window with
`info.representation = "contact_window"`, `balanced = false`, full `chrom_sizes`,
and a positive `resolution`. Both axes need matching ordered `bin1_chrom/start/end`
and `bin2_chrom/start/end`, assigned to their dimensions in `axis_info`. Coordinates
are zero-based, half-open, fixed-width bins (the last chromosome bin may be shorter).
The existing contact-window selector now preserves chromosome lengths.

Balanced, log, observed/expected, missing, negative, fractional or asymmetric data
are rejected. Counts above 2^24 per pixel are rejected to avoid silent precision
loss in HIC floating-point storage. No normalization vectors are generated. A
window export records its partial coverage in a companion `.metadata.json` file:
unexported regions must not be interpreted as measured zeros. Use the whole Cooler
for whole-genome browsing. Assembly labels do not verify the assembly of the input.

Contact writers use `buffer_mb` and task-local temporary storage; estimates include
compression overhead and the genome-wide bin table. This is not a strict cap on
native-code RSS; existing process limits/emergency spill remain in force. Cancellation
is checked between batches; native finalization may finish before cooperative cancellation.

## GenBank, tracks, networks and trees

- `genbank`: `info.genbank_records` contains complete original strings aligned to
  the first axis. `GenBankReader` retains them by default, including sequence,
  feature locations, qualifiers and topology. `retain_records: false` restores
  summary-only reading. Alternatively supply DNA `info.sequences`, assigned in
  `axis_info`, first-axis record IDs, and `topology` (`linear` or `circular`). This
  path adds no invented annotations. Preserved record text is authoritative;
  editing numeric summary fields does not edit its sequence/annotations.
- `bed`/`bedgraph`: declare `info.coordinate_system = "0-based-half-open"` and
  aligned `chrom`, `start`, `end`. `value_column` selects a zero-based numeric
  column for bedGraph. BED export is BED3, not a reconstruction of optional fields.
- `graphml`: declare `info.representation = "adjacency"`. Both axes need identical
  ordered labels. Undirected matrices must be symmetric; set `directed` for
  directed edges. Zero means no edge. Correlation/distance matrices are not
  automatically treated as networks.
- `newick`: supply a complete semicolon-terminated tree in `info.newick`. Branch
  lengths and labels are preserved and parsed before export.

The dependencies (`hictkpy`, `h5py`, Biopython, NumPy) use the existing dependency
manager and conflict isolation. Imports are lazy; the declaration is operator-wide,
so dependency repair may install all four even for a CSV-only use. V3 is unchanged.

## Opening specialist viewers

The updated application results panel offers **Open with** for retained files.
Desktop applications come first; browser tools are explicit manual-import links.
Availability, file loading and scientific interpretation are separate checks.
Older applications still read/copy these ordinary files but do not gain the new
viewer menu from a library-only update. See
[the viewer catalog and API tutorial](../../../../../../docs/result_viewers.md).
Remote execution saves results on the server; desktop handoff fetches the selected
output and its retained index siblings to the client.

## Examples

For a matrix named `counts`, run these steps in a manifest:

```yaml
steps:
  - name: export_results
    inputs: [counts]
    params: {output: counts_csv, format: csv}
  - name: describe
    inputs: [counts]
```

The first branch creates CSV; the second continues analysis of the same matrix.
For ProteinMPNN output `designs`, use `format: fasta` to export only sequences,
or `format: native` for both original sequences and score table. For RFdiffusion,
use `format: pdb` to export all generated backbones.

## Validation

Regression tests cover managed-memory branching, labels, safe NPY round trips,
FASTA alignment, native path reuse, external copies and old-application file
viewing. Protein design file adapters use synthetic tool outputs in these tests;
this does not constitute a validation of model quality.
