<!-- operon:generated -->
# Bin

## Purpose

> Discretize a continuous axis into bins.
>
> For each position along ``dim``, computes a bin index by cutting the
> values along the other axes into equal-width or equal-frequency
> intervals. The output has one row per position along ``dim`` and a
> single integer bin id per row.
>
> This is the standard way to turn a continuous quantity (age,
> expression, allele frequency, distance) into a categorical one that
> can be used by grouping operators such as ``aggregate`` or
> ``compare_groups``.
>
> Value per position
> ------------------
> Two ways to decide the value used to bin each position:
>
> 1. ``value_label`` : if given, the operator reads that column from
>    the "other" axis (the one that is not ``dim``) and uses its
>    values directly. This is the right choice when the input is a
>    table whose second axis is a "statistic" axis with a single
>    named column.
>
> 2. ``stat`` : if ``value_label`` is not given, the operator
>    summarizes each position's values along the other axes with one
>    of the following statistics:
>
>        mean      mean over the other axes (default)
>        median    median over the other axes
>        min       minimum
>        max       maximum
>        first     first non-missing value
>
> Missing cells are excluded from the summary.
>
> Methods
> -------
>     quantile  equal-frequency bins: each bin holds roughly the same
>               number of positions (default)
>     uniform   equal-width bins: the value range is split into N
>               equal intervals
>
> Layout
> ------
>     input   dims: [..., dim, ...]  (any ndim >= 1)
>     output  dims: [dim, "bin"]
>
> NaNs and out-of-range values
> ----------------------------
> Positions whose value is NaN get bin id -1. Positions outside the
> observed range (only possible with ``uniform``) get clamped to the
> nearest bin.
>
> Params:
>     dim          : dimension to bin along (required)
>     bins         : number of bins (default 10)
>     method       : "quantile" | "uniform" (default "quantile")
>     value_label  : optional column label on the other axis; if
>                    given, that column's values are used directly
>     stat         : summary name (default "mean"), ignored when
>                    ``value_label`` is given
>     output       : context key for the result (default: step name)
>
> Discretize a continuous axis into bins.

## Inputs and outputs

Kind: `operator`. Operator ID: `bin`.
Input count: `1`.
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

Implementation: `src/task/step/steps/bin.py` (`BinStep`).
