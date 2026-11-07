<!-- operon:generated -->
# Boxplot

## Purpose

> Boxplot of one value column split by groups.
>
> Inputs
> ------
> 0. Data form with a value dim (typically the observation dim) and a
>    sample dim.
> 1. Metadata form with the same sample dim and a column that carries
>    the group labels.
>
> The sample axis is aligned by label between the two forms. For each
> group, one box is drawn for the selected value column.
>
> Domain-agnostic. Any 2D data form + any 2D metadata form works.
>
> Params:
>     dim          : dim of the data form that holds the value column
>                    (default "feature")
>     value_label  : column label to plot (required)
>     group_dim    : sample dim shared by both forms (required)
>     group_label  : column label on the metadata's other dim
>                    (required)
>     groups       : optional list of group names to keep, in order
>     filename     : output file name (required)
>     title        : optional plot title
>     xlabel       : optional x label (default: group_label)
>     ylabel       : optional y label (default: value_label)
>     show_points  : overlay individual points (default True)
>     point_size   : marker size for overlay (default 4)
>     point_alpha  : marker transparency (default 0.5)
>
> Boxplot of one value column split by groups.

## Inputs and outputs

Kind: `operator`. Operator ID: `boxplot`.
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

Implementation: `src/task/step/steps/boxplot.py` (`BoxplotStep`).
