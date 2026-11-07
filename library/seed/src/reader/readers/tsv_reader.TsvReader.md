<!-- operon:generated -->
# TsvReader

## Purpose

> TSV reader.
>
> Tab-separated two-dimensional tables. The first line is treated as
> a header by default; set ``header: false`` in args to read every
> line as data.
>
> Compression (.gz, .bz2, .xz) is handled by pandas directly; this
> reader receives the original path.
>
> Label rules accepted:
>
>     builtin           header row (valid only for the column dim)
>     auto              position indices "0", "1", ...
>     {<col_dim>: <k>}  read column <k>; its values become the row
>                       labels and the column is removed from data.
>                       ``k`` is a position in the original file,
>                       independent of ``columns``.
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``auto``. Duplicate labels are
> disambiguated by appending ``#<position>``.
>
> Column selection
> ----------------
> ``columns`` restricts the reader to a subset of header names, in the
> order given. ``labels`` indices still refer to the original file.
>
> Info columns
> ------------
> ``info_columns`` maps a header name to an info field name. The column
> is read verbatim as strings into ``info[field]`` and declared parallel
> to the row dimension in ``axis_info``. The column is removed from
> data.
>
> Non-numeric columns are encoded. The encoder instance used for each
> column is recorded in ``info["encoders"]`` as
> ``{col_dim: {label: encoder}}``.
>
> Info fields set:
>
>     missing_code      np.nan
>     encoders          present only when a column was encoded
>     <info_columns>    one entry per declared info column
>
> Reader for .tsv files.

## Inputs and outputs

Kind: `reader`. Operator ID: `TsvReader`.
This Reader opens files with extensions: `.tsv`.
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

Implementation: `src/reader/readers/tsv_reader.py` (`TsvReader`).
