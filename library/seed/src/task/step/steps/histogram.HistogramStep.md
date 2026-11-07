<!-- operon:generated -->
# 直方图

## Purpose

> Histogram operator.
>
> Input is a single 2D form. One dimension of the form holds the
> attributes (columns); the other dimension holds the observations.
>
> The operator reads one labeled column and plots its distribution.
>
> Draw a histogram.
>
> Params:
>     dim         : attribute dimension (default "feature")
>     value_label : column label for the values
>     bins        : number of bins (default 40)
>     filename    : output file name
>     title       : optional plot title
>     xlabel      : optional x-axis label (default: value_label)
>     ylabel      : optional y-axis label (default: "Count")
>     log_y       : use log scale on the y axis (default False)

## Inputs and outputs

Kind: `operator`. Operator ID: `histogram`.
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

Implementation: `src/task/step/steps/histogram.py` (`HistogramStep`).
