<!-- operon:generated -->
# 低表达过滤

## Purpose

> Filter positions along one dimension by a minimum value.
>
> Keeps positions whose value reaches ``min_value`` in at least
> ``min_samples`` samples. Domain-agnostic: works on any 2D form.
>
>     pass[i, j] = valid[i, j] and data[i, j] >= min_value
>     keep[i]    = sum_j(pass[i, j]) >= min_samples
>
> Missing values never count as a passing sample.
>
> Params:
>     dim         : dimension to filter along
>     min_value   : per-sample threshold (default 1)
>     min_samples : minimum number of samples that must pass
>                   (default 1)
>     output      : context key for the result (default: step name)
>
> Drop positions that do not reach a minimum value.

## Inputs and outputs

Kind: `operator`. Operator ID: `filter_min`.
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

Implementation: `src/task/step/steps/filter_min.py` (`FilterMinStep`).
