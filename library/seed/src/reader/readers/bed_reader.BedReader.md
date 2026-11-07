<!-- operon:generated -->
# BedReader

## Purpose

> UCSC BED reader.
>
> A whitespace-delimited text file with 3 to 12 columns per line. No
> header. Column meaning is fixed by the BED specification:
>
>     0  chrom         chromosome name
>     1  chromStart    0-based start
>     2  chromEnd      end (exclusive)
>     3  name          feature name
>     4  score         0-1000
>     5  strand        '+' or '-'
>     6  thickStart
>     7  thickEnd
>     8  itemRgb       R,G,B
>     9  blockCount
>     10 blockSizes    comma-separated
>     11 blockStarts   comma-separated
>
> ``track`` and ``browser`` lines at the top are skipped.
>
> Compression is handled by the framework; this reader sees plain
> files only.
>
> Label rules accepted:
>
>     builtin           the standard BED column names above
>     auto              position indices "0", "1", ...
>     {<other_dim>: <k>}  read column <k> as the other dim's labels
>                         (removed from data)
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``auto``. Duplicate labels are
> disambiguated by appending ``#<position>``.
>
> Non-numeric columns (chrom, name, strand, ...) are encoded. The
> encoder instance used for each column is recorded in
> ``info["encoders"]``.
>
> Reference
> ---------
> UCSC BED format: https://genome.ucsc.edu/FAQ/FAQformat.html#format1
> GA4GH BED v1.0 formalises the same layout.
>
> Info fields set:
>
>     missing_code      np.nan
>     encoders          present only when a column was encoded
>
> Reader for UCSC .bed files.

## Inputs and outputs

Kind: `reader`. Operator ID: `BedReader`.
This Reader opens files with extensions: `.bed`.
Read the structured `contracts` section before connecting nodes. It includes
the accepted data types, dimension constraints and output propagation rule.

## Parameter guidance

The adjacent parameter JSON owns defaults, valid choices, ranges and required
fields. Request the generated `parameters` section and `parameters_schema` for
the exact interface; do not infer parameter names from prose.
Saved routes keep their own parameter values independently of current defaults.

## Interpretation

Check output metadata and labels before downstream analysis. The declared output
contract describes the representation; it does not establish biological validity
or statistical assumptions for a particular dataset.

## Runtime environment

Runs in the shared Operon interpreter.

## Limitations

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/reader/readers/bed_reader.py` (`BedReader`).
