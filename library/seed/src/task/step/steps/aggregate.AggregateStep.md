<!-- operon:generated -->
# Aggregate

## Purpose

> Aggregate positions along one axis by group.
>
> Two inputs share an axis (the "row" axis). The first input carries
> values; the second carries a group label for each position. For
> each group, the operator collapses all positions in that group
> into a single row by applying a reduction (sum, mean, median, ...).
>
> This is the natural companion of ``join``: where ``join`` attaches
> metadata columns to a form, ``aggregate`` reduces a form by a
> metadata column. Typical uses:
>
>     - collapse species to genus before plotting composition
>     - collapse cells to clusters before profiling
>     - collapse genes to pathways before scoring
>     - collapse any [row, other] matrix by a [row, group] table
>
> Layout
> ------
>     data    dims: [row_dim, other_dim]   (any two axes)
>     groups  dims: [row_dim, group_dim]   (same row_dim first)
>     output  dims: [group_dim, other_dim]
>
> Both inputs must be 2D with ``dim`` as their first axis. To use a
> form whose shared axis is second, transpose it first.
>
> Reductions
> ----------
>     sum       sum of values in the group
>     mean      mean of values in the group
>     median    median of values in the group
>     min       minimum
>     max       maximum
>     count     number of non-missing values in the group
>
> Missing cells are excluded before the reduction, except for
> ``count`` where they are dropped from the count.
>
> Group labels
> ------------
> The group column can be a numeric column (each value is used as a
> group key) or an encoded string column (the encoder's inverse map
> is used to recover group names). The output group labels are the
> recovered names, sorted by first appearance in the input order.
>
> Params:
>     dim        : shared dim name (required)
>     group_col  : column label on the groups form (required)
>     method     : reduction name (default "sum")
>     output     : context key for the result (default: step name)
>
> Aggregate positions along one axis by group.

## Inputs and outputs

Kind: `operator`. Operator ID: `aggregate`.
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

Implementation: `src/task/step/steps/aggregate.py` (`AggregateStep`).
