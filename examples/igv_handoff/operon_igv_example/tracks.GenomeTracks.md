# Export genome tracks

## Purpose

Transfer `interval_merge` output into interoperable BED and bedGraph files.
IGV is one consumer; it is not needed to run this operator. Install this optional
SDK example independently of the built-in operator library.

## Inputs

One numeric `merged_intervals` Form. The second axis must have named `start`,
`end`, and the selected value columns. The first axis must declare `chrom` in
`axis_info`, and `info.chrom` must contain the chromosome for every row.
The exporter does not infer chromosomes or convert coordinate conventions.

Coordinates must be exact, non-negative integers with `start < end`. Input must
be sorted by chromosome name, then start, and must not overlap within each
chromosome. `interval_merge` produces this ordering. Zero-based, half-open
coordinates are used for both outputs. Floating coordinates beyond 2^53 are
rejected because their original integer identity is not reliably recoverable.

## Outputs

A `genome_tracks` FileArtifact has `bed`, `bedgraph` and `provenance` roles.
BED contains merged intervals. bedGraph uses the selected numeric statistic;
the default `n_intervals` is the count of source intervals per merged region.
It is **not read coverage, normalized expression, or an enrichment score**.
The provenance JSON records the assembly, convention, column, rows and file hashes.
The enclosing Operon job preserves its operator pins and independent parameters JSON.

## Parameters

The authoritative parameter schema is the adjacent `tracks.parameters.json`.
Set `assembly` explicitly and open the matching reference in IGV. `prefix` names
a run-local artifact directory; it is not an arbitrary output filesystem path.

## Memory and cancellation

The input remains managed by Operon's existing planner. The exporter writes
rows through two 64 KiB buffers and returns small file references; it does not
copy or sort the matrix. It declares full-input execution, not a streaming
operator protocol. Cancellation is checked every 1024 rows and at completion.
The upstream `interval_merge` still requires its full admitted input. This
example does not claim an out-of-core genomic interval merge or a universal
disk-quota adapter for external file tools.

## Example

Connect `BedReader` → `interval_merge` → `example.genome_tracks`. Set
`assembly` to the reference identity, retain the final output, then use the
artifact API's `file?role=bed` and `file?role=bedgraph` endpoints. The repository's
`scripts/accept_igv_handoff.py` performs this workflow with two synthetic
chromosomes and generates a portable session for desktop IGV validation.
