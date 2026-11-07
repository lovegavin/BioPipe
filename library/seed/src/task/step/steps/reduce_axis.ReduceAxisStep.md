<!-- operon:generated -->
# Axis statistics

## Purpose

> Reduce one axis of a form to summary statistics.
>
> For each position along ``dim``, computes one or more summary
> statistics over all other axes, and returns a new form in which
> ``dim`` is replaced by a ``"statistic"`` axis.
>
> Layout
> ------
>     input  dims: [..., dim, ...]     (any ndim >= 1)
>     output dims: [..., "statistic"]  (dim removed)
>
> The reduced dim is removed; every other dim keeps its original
> order; the new ``"statistic"`` axis is appended last.
>
> Supported statistics
> --------------------
>     sum        sum of values
>     mean       mean of values
>     std        standard deviation
>     var        variance
>     min        minimum
>     max        maximum
>     median     median
>     nonzero    number of non-zero values
>     count      number of non-missing values
>
> Missing cells are identified via ``info["missing_code"]`` when set
> and finite, otherwise via NaN. Every statistic except ``count`` and
> ``nonzero`` excludes missing cells; ``count`` and ``nonzero`` count
> only non-missing cells.
>
> Axis-parallel info for the reduced dim (as declared in
> ``axis_info[dim]``) is dropped from the output. Info entries for
> surviving dims pass through unchanged. ``info["encoders"]`` is
> trimmed to surviving dims.
>
> Params:
>     dim     : dimension to reduce (required)
>     stats   : statistic name, or list of names (required)
>     output  : context key for the result (default: step name)
>
> Reduce one axis of a form to summary statistics.

## Inputs and outputs

Kind: `operator`. Operator ID: `reduce_axis`.
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

Implementation: `src/task/step/steps/reduce_axis.py` (`ReduceAxisStep`).
