<!-- operon:generated -->
# prioritize

## Purpose

> Keep the top positions along an axis, ranked by an info field.
>
> Positions are sorted by a numeric info field declared parallel to
> ``dim``. The top ``top_n`` are retained. Their order in the output
> matches their order in the source, so downstream label alignment
> stays stable.
>
> This pairs with ``annotate``: annotate writes reference columns into
> ``info``; prioritize selects the positions whose annotation matters
> most.
>
> Layout
> ------
>     input   dims: [..., dim, ...]
>     output  dims: same as input, with ``dim`` shortened to ``top_n``
>
> Ranking
> -------
> Missing values (NaN) are ranked last regardless of direction.
> Ties keep their source order (stable sort).
>
> Params:
>     dim        : dimension to sort along (required)
>     by         : info field to rank by (required)
>     top_n      : number of positions to keep (required)
>     ascending  : False ranks largest first (default); True ranks
>                  smallest first
>     output     : context key for the result (default: step name)
>
> Keep the top positions along a dimension, ranked by an info field.

## Inputs and outputs

Kind: `operator`. Operator ID: `prioritize`.
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

Implementation: `src/task/step/steps/prioritize.py` (`PrioritizeStep`).
