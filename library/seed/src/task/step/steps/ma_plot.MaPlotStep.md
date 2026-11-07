<!-- operon:generated -->
# MA plot

## Purpose

> MA plot of a differential comparison result.
>
> X axis: A = (mean_a + mean_b) / 2
> Y axis: M = log2FC
> Points are colored by P < p_threshold.
>
> Input is a 2D form with a feature dim and a "statistic" dim that
> carries log2FC, mean_a, mean_b, and P.
>
> Params:
>     dim           : feature dim (default "gene")
>     stat_dim      : statistic dim (default "statistic")
>     lfc_label     : column label for log2FC (default "log2FC")
>     mean_a_label  : column label for group A mean (default "mean_a")
>     mean_b_label  : column label for group B mean (default "mean_b")
>     p_label       : column label for P (default "P")
>     p_threshold   : P cutoff for significance (default 0.05)
>     filename      : output file name (required)
>     title         : optional plot title
>     xlabel        : optional x label (default "log2 mean")
>     ylabel        : optional y label (default: lfc_label)
>     point_size    : marker size (default 8)
>     alpha         : marker transparency (default 0.7)
>     label_top     : if > 0, annotate the top N most significant
>                     points with their feature labels (default 0)
>
> Draw an MA plot.

## Inputs and outputs

Kind: `operator`. Operator ID: `ma_plot`.
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

Implementation: `src/task/step/steps/ma_plot.py` (`MaPlotStep`).
