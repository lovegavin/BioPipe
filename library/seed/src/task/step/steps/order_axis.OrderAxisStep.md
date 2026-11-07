<!-- operon:generated -->
# order_axis

## Purpose

> Reorder every position along an axis by an info field.
>
> Unlike ``prioritize``, which keeps only the top N positions,
> ``order_axis`` keeps every position and only changes their order.
> The set of labels is unchanged; their positions along ``dim`` are
> reassigned according to the ranking.
>
> Typical uses: sort variants by genomic position before plotting,
> sort samples by a covariate, sort features by variance before a
> heatmap.
>
> Layout
> ------
>     input   dims: [..., dim, ...]
>     output  dims: same as input, ``dim`` reordered
>
> Params:
>     dim        : dimension to reorder (required)
>     by         : numeric info field declared parallel to ``dim``
>                  (required)
>     descending : True ranks largest first; False ranks smallest
>                  first (default)
>     output     : context key for the result (default: step name)
>
> Reorder an axis by a numeric info field, keeping all positions.

## Inputs and outputs

Kind: `operator`. Operator ID: `order_axis`.
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

Implementation: `src/task/step/steps/order_axis.py` (`OrderAxisStep`).
