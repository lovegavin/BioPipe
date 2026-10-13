# Importing data in Studio

The input node accepts every format in the reader registry. The file picker and
server use reader descriptors, so optional parsing packages do not need to be
installed to upload files, configure an input, save a canvas, or export a workflow.
Actual execution still requires the selected reader's dependencies and valid data.
An upload confirms file transfer and dataset structure, not successful parsing.

Choose **Select data files** in the input inspector. Select one dataset at a time:

| Reader | Main file | Additional files in the same selection |
| --- | --- | --- |
| CSV | `.csv` | None |
| Text | `.txt`, `.tsv`, `.tab` | None; tab-separated by default |
| BED intervals | `.bed` | None; this is distinct from binary PLINK BED |
| GFF3 / GTF | `.gff`, `.gff3`, `.gtf` | None |
| FASTA | `.fasta`, `.fa`, `.fna`, `.faa` | None |
| AnnData | `.h5ad` | None |
| Parquet | `.parquet` | None |
| BGEN | `.bgen` | None; the current reader uses embedded sample identifiers |
| VCF | `.vcf`, `.vcf.gz` | None |
| PLINK 1 | `cohort.bed` | `cohort.bim` and `cohort.fam` |
| PLINK 2 | `cohort.pgen` | `cohort.pvar` and `cohort.psam` |
| 10x MTX | `.mtx` or `.mtx.gz` | `barcodes.tsv` and `features.tsv` (or `genes.tsv`); either companion may have `.gz` appended |

CSV, text, BED intervals, GFF3, GTF and FASTA also accept `.gz`, `.bz2` and `.xz`
wrappers. Compression is advertised only when the current reader can handle it;
an arbitrary `.gz` or `.zst` file is not automatically a supported input. PLINK
triplets use uncompressed files with matching, case-sensitive basenames and
lowercase companion extensions, matching the runtime's sibling lookup.

Each upload gets its own directory. Original filenames remain intact within it,
so sibling lookup works and repeated filenames from separate imports cannot
overwrite each other. Files stream to disk without an application-imposed size
limit by default; upload size is independent of the analysis memory budget.
To explicitly impose a per-file cap, set `BIOPIPE_STUDIO_MAX_UPLOAD_MB` to a positive
integer in MiB before starting Studio. Both desktop and development launchers use
this setting; unset or `0` means no configured cap. Disk capacity and filesystem
limits still apply. Failed transfers remove partial files; a failed batch
is cancelled by the client. An interrupted browser/server may leave an unpublished
batch directory, which is not attached to a canvas. To avoid copying large data,
use an existing path within the workspace. Stored source paths are relative to the
canvas base directory; no machine-specific paths are embedded.

Uploading replaces the input's path, dimensions, label rules and reader arguments
with the selected reader's suggested defaults. Review them before execution,
especially table headers and sample identifiers. Existing saved canvases and YAML
sources retain their values until the user explicitly chooses replacement data.

Dimension names accept English and Chinese commas. Editing preserves trailing
commas and spaces while the saved source contains a trimmed list of nonempty names.

## Reader extension metadata

Readers can optionally declare `file_input`; `describe_reader()` copies it into
the registry without importing optional parsing dependencies:

```python
class CountsReader(Reader):
    extensions = [".counts"]
    handles_compression = False
    file_input = {
        "dims": ["gene", "sample"],
        "labels": {"gene": "builtin", "sample": "builtin"},
        "compression": [".gz", ".bz2", ".xz"],
        "companions": [["samples.tsv", "samples.tsv.gz"]],
    }
```

`companions` is a list of required groups; exactly one filename from each group
must be selected. Existing `requires_siblings` and `excludes_siblings` declarations
continue to control same-basename matching. `compression` contains supported
outer suffixes, not a request to install codecs. If absent, framework-decompressed
readers get gzip/bzip2/xz, while readers handling their own compression get no
outer suffixes. Without `file_input`, dimensions default to `sample, feature` and
labels default to `auto`. Old plugin descriptors remain supported.

## Upload API

All mutations use the existing Studio session token.

1. `POST /api/assets/batches` with `{"filenames": [...]}` validates one dataset
   and returns a batch `id`, reader name and suggested source configuration.
2. For each file, `POST /api/assets?batch=<id>&filename=<name>` streams its raw
   bytes as `application/octet-stream`. Keep the original filenames.
3. `POST /api/assets/batches/<id>/complete` with `{"base_dir": "."}` publishes
   the batch and returns `source`, `reader`, `filename` and `files`.
4. On failure, `POST /api/assets/batches/<id>/cancel` removes unpublished data.
   Completed batches cannot be deleted through this endpoint.

The existing single-file `POST /api/assets?filename=...` endpoint remains
compatible and now accepts any complete, registered single-file input.

## Reader controls and dimension names

The inspector renders Reader parameters from the public descriptor: CSV header and
separator, H5AD layer, text delegate and encoding configuration. Readers without
extra options say so explicitly. Advanced JSON remains available for plugin-specific
and nested options. An ambiguous path such as `.bed` does not guess a Reader form.

Dimension edits commit on blur or Enter. Axis label keys and cross-axis label rules
are renamed together by position; duplicate or empty dimension names are rejected.
New dimensions get `auto` labels. Removing an axis removes its label rule.

H5AD/MTX preparation under memory management uses bounded disk blocks; see
[Resource runtime](resource_runtime.md#two-phase-source-preparation). Upload, parser
availability, preparation and operator execution remain distinct stages.
