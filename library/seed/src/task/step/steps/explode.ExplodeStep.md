<!-- operon:generated -->
# explode

## Purpose

> Expand a multi-valued info field into separate positions.
>
> When an info field declared parallel to ``dim`` contains a list per
> position (for example semicolon-separated GO terms), this step
> creates one output position per element. Other axes are replicated.
>
> This is the standard way to turn a one-to-many annotation into a
> long table that downstream grouping operators can consume.
>
> Layout
> ------
>     input   dims: [..., dim, ...]
>     output  dims: same, with ``dim`` expanded
>
> Params:
>     dim        : dimension whose info field is exploded (required)
>     field      : info field name declared parallel to ``dim``
>                  (required)
>     sep        : separator inside each cell (default ";")
>     keep_empty : keep positions whose field is empty (default False)
>     output     : context key for the result (default: step name)
>
> Expand a multi-valued info field into separate positions.

## Inputs and outputs

Kind: `operator`. Operator ID: `explode`.
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

Implementation: `src/task/step/steps/explode.py` (`ExplodeStep`).
