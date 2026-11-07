<!-- operon:generated -->
# Forest plot

## Purpose

> Forest plot of hazard ratios from a Cox regression result.
>
> Input is the 2D form produced by ``cox_regression``: one row per
> covariate, one column per statistic. The operator draws a horizontal
> forest plot with one line per covariate, showing the point estimate
> of HR and its 95% confidence interval.
>
> The reference line is HR = 1 (log scale). Covariates whose CI does
> not cross the reference line are highlighted.
>
> Params:
>     dim         : covariate dim (default "covariate")
>     stat_dim    : statistic dim (default "statistic")
>     hr_label    : column with HR (default "HR")
>     low_label   : column with lower CI (default "CI_low")
>     high_label  : column with upper CI (default "CI_high")
>     p_label     : column with p-value (default "P")
>     filename    : output file name (required)
>     title       : optional plot title
>     xlabel      : optional x-label (default "Hazard ratio (95% CI)")
>     xlim        : optional [x_min, x_max] on the HR scale
>     log_scale   : use log scale on x (default True)
>     color_sig   : color for significant rows (default "#D62728")
>     color_ns    : color for non-significant rows (default "#4C72B0")
>     sort_by    : "input" | "hr" | "p" (default "input")
>
> Draw a forest plot of hazard ratios.

## Inputs and outputs

Kind: `operator`. Operator ID: `forest_plot`.
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

Implementation: `src/task/step/steps/forest_plot.py` (`ForestPlotStep`).
