<!-- operon:generated -->
# Filter by metrics

## Purpose

> Filter one axis of a form using thresholds on a second form.
>
> Two inputs share a dim (the filter dim). The first input is the data
> form; the second is a metrics form whose positions along the shared
> dim carry one or more statistics. The operator keeps, along the data
> form's shared dim, only the positions that satisfy every rule.
>
> Layout
> ------
>     data     dims: [..., dim, ...]   (any ndim >= 1)
>     metrics  dims: [dim, "statistic"]   (2D)
>     output   dims: same as data, but dim is subset
>
> Rules
> -----
> Each rule is a mapping:
>
>     {field: <name>, min: <float>}   keep positions with value >= min
>     {field: <name>, max: <float>}   keep positions with value <= max
>     {field: <name>, min: <float>, max: <float>}   both
>
> ``field`` must be a label on the metrics form's ``statistic`` dim.
> The metrics form's ``dim`` labels must all appear in the data form's
> ``dim`` labels; extra positions on either side are ignored.
>
> Missing values
> --------------
> A missing value in the metrics form never satisfies a min/max rule;
> the position is dropped, and the drop is recorded in the export.
>
> Params:
>     dim      : shared dim name (required)
>     rules    : list of rule mappings (required, non-empty)
>     output   : context key for the result (default: step name)
>
> Keep positions along a dim that satisfy thresholds from another form.

## Inputs and outputs

Kind: `operator`. Operator ID: `filter_by`.
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

Implementation: `src/task/step/steps/filter_by.py` (`FilterByStep`).
