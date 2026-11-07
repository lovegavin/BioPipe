<!-- operon:generated -->
# MtxReader

## Purpose

> MatrixMarket MTX reader (10x Genomics MEX format).
>
> A MEX triplet:
>
>     matrix.mtx      sparse count matrix (gene x cell)
>     barcodes.tsv    cell barcodes (columns)
>     features.tsv    gene features (rows), or genes.tsv in old layouts
>
> The three files must live in the same directory. The reader is
> triggered by pointing at the .mtx file. Each of the three may be
> independently gzip-compressed; compression is detected by magic
> bytes, not extension.
>
> Per the 10x Genomics documentation, each element of the matrix is
> the number of UMIs associated with a feature (row) and a barcode
> (column). MatrixMarket coordinate format is 1-based.
>
> The reader declares ``handles_compression = True`` because siblings
> must be read from the original directory, not from a temporary file.
>
> Label rules accepted:
>
>     builtin           gene: features.tsv col 0
>                       cell: barcodes.tsv
>     auto              position indices "0", "1", ...
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``builtin``. Duplicate labels are
> disambiguated by appending ``#<position>``.
>
> Identifiers remain string axis labels, separate from the numeric count matrix.
>
> Reference
> ---------
> 10x Genomics MEX format:
> https://support.10xgenomics.com/single-cell-gene-expression/software/pipelines/latest/output/matrices
>
> Info fields set:
>
>     missing_code      np.nan
>
> Reader for MatrixMarket .mtx files.

## Inputs and outputs

Kind: `reader`. Operator ID: `MtxReader`.
This Reader opens files with extensions: `.mtx`.
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

Declared memory modes: full, disk. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/reader/readers/mtx_reader.py` (`MtxReader`).
