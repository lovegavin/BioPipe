<!-- operon:generated -->
# 缺失值填补

## Purpose

> Impute missing values in a form.
>
> Fills missing cells using a simple strategy. Common in proteomics
> and metabolomics, where missing values are frequent (low-abundance
> features fall below the detection limit).
>
> Methods
> -------
>     min     replace every missing cell with (global minimum *
>             ``min_scale``). This is the Perseus "replace by minimum"
>             strategy.
>     median  replace each missing cell with the median of its feature,
>             computed over all other axes.
>     mean    replace each missing cell with the mean of its feature,
>             computed over all other axes.
>
> The ``dim`` parameter names the feature axis. For ``median`` and
> ``mean``, the statistic is computed over every axis except ``dim``.
> For ``min``, the statistic is the global minimum over the whole
> matrix.
>
> The operator works on any dimensionality >= 1. ``median`` and
> ``mean`` require at least one axis besides ``dim`` to aggregate
> over; for 1D input, use ``method="min"``.
>
> Missing cells are identified via ``info["missing_code"]`` when set
> and finite, otherwise via NaN. The output has the same dims, labels,
> info and axis_info as the input; only ``data`` is replaced.
>
> Params:
>     method     : "min" | "median" | "mean" (required)
>     dim        : feature dim (required)
>     min_scale  : multiplier for the min method (default 1.0)
>     output     : context key for the result (default: step name)
>
> Fill missing values in a form.

## Inputs and outputs

Kind: `operator`. Operator ID: `impute`.
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

Implementation: `src/task/step/steps/impute.py` (`ImputeStep`).
