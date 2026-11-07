<!-- operon:generated -->
# ParquetReader

## Purpose

> Parquet reader.
>
> A two-dimensional columnar table. Column names come from the Parquet
> metadata; there is no header-line concept and no ``header`` arg.
>
> Parquet internal compression is handled by pyarrow. External compression
> wrappers are decompressed to disk by the framework before parsing.
>
> Label rules accepted:
>
>     builtin           column names from Parquet metadata
>     auto              position indices "0", "1", ...
>     {<col_dim>: <k>}  read column <k>; its values become the row
>                       labels and the column is removed from data
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``auto``. Duplicate labels are
> disambiguated by appending ``#<position>``.
>
> A Parquet file may carry an index. If it does, it is treated as the
> first column.
>
> Non-numeric columns are encoded. The encoder instance used for each
> column is recorded in ``info["encoders"]`` as
> ``{col_dim: {label: encoder}}``.
>
> Info fields set:
>
>     missing_code      np.nan
>     encoders          present only when a column was encoded
>
> Reader for .parquet files.

## Inputs and outputs

Kind: `reader`. Operator ID: `ParquetReader`.
This Reader opens files with extensions: `.parquet`.
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

Implementation: `src/reader/readers/parquet_reader.py` (`ParquetReader`).
