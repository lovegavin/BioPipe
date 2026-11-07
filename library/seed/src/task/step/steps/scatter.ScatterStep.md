<!-- operon:generated -->
# 散点图

## Purpose

> Scatter plot operator.
>
> Input is a single 2D form. One dimension of the form holds the
> attributes (columns); the other dimension holds the observations
> (points).
>
> The operator reads two labeled columns as x and y, optionally a third
> as a color group, and writes a scatter plot to ``output/figures/``.
>
> Draw a scatter plot.
>
> Params:
>     dim         : attribute dimension (default "feature")
>     x_label     : column label for the x axis
>     y_label     : column label for the y axis
>     color_label : optional column label for grouping
>     filename    : output file name (e.g. "pca.png")
>     title       : optional plot title
>     xlabel      : optional x-axis label (default: x_label)
>     ylabel      : optional y-axis label (default: y_label)
>     point_size  : marker size (default 8)
>     alpha       : marker transparency (default 0.7)

## Inputs and outputs

Kind: `operator`. Operator ID: `scatter`.
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

Implementation: `src/task/step/steps/scatter.py` (`ScatterStep`).
