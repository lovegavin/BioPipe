<!-- operon:generated -->
# Join

## Purpose

> Join two forms along a shared dim by label.
>
> Attaches selected columns from a "metadata" form to a "data" form.
> Both forms must have the shared dim as their first axis. The
> columns of the metadata form are appended to the data form's second
> axis, so the output is a wider form whose labels combine the two.
>
> This is the natural way to bring grouping columns next to the
> values they describe, e.g. to color a scatter plot, to split a
> barplot, or to feed a violin plot.
>
> Alignment
> ---------
>     inner   keep rows whose label is present in both forms
>     left    keep rows whose label is present in the data form,
>             filling meta cells with NaN when the row is missing
>             from the metadata form
>
> Both forms must be 2D with the shared dim as the first axis. To use
> a form whose shared dim is second, transpose it first.
>
> Output
> ------
>     dims    = [shared_dim, <data_other_dim>]
>     labels  = {shared_dim:  <common row labels>,
>                <data_other_dim>: {<data_feature>: pos,
>                                   <selected_meta_column>: pos, ...}}
>
> Feature labels that already exist in the data form are rejected
> unless a ``prefix`` is given.
>
> Params:
>     dim      : shared dim name (required)
>     columns  : list of column labels from the metadata to attach,
>                or "all" (default "all")
>     how      : "inner" | "left" (default "inner")
>     prefix   : optional string prepended to attached column names
>     output   : context key for the result (default: step name)
>
> Join two forms along a shared dim by label.

## Inputs and outputs

Kind: `operator`. Operator ID: `join`.
Input count: `2`.
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

Implementation: `src/task/step/steps/join.py` (`JoinStep`).
