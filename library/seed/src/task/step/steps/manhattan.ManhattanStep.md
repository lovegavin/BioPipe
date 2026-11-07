<!-- operon:generated -->
# 曼哈顿图

## Purpose

> Manhattan plot operator.
>
> Input is a single 2D form. The operator draws a genome-wide scatter
> of -log10(P) against cumulative genomic position.
>
> Field locations
> ---------------
> Each field is looked up either as a data column on a named dimension
> or as an axis-parallel info entry. ``chrom_label`` and ``pos_label``
> are looked up on ``dim``; ``p_label`` is looked up on ``p_dim``
> (default: ``dim``). This lets chromosome/position come from one
> dimension and the P value from another.
>
> Chromosome values are kept as they appear (typically strings such as
> ``"22"``). They are grouped, ordered and labelled verbatim; no
> encoding is applied.
>
> Draw a Manhattan plot.
>
> Params:
>     dim         : observation dim (one point per position)
>     chrom_label : chromosome field on ``dim``
>     pos_label   : position field on ``dim``
>     p_label     : P-value field
>     p_dim       : dim carrying ``p_label`` (default: ``dim``)
>     filename    : output file name
>     threshold   : optional P threshold for a horizontal line
>     title       : optional plot title
>     point_size  : marker size (default 6)
>     alpha       : marker transparency (default 0.85)

## Inputs and outputs

Kind: `operator`. Operator ID: `manhattan`.
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

Implementation: `src/task/step/steps/manhattan.py` (`ManhattanStep`).
