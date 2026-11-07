<!-- operon:generated -->
# Cox

## Purpose

> Cox proportional hazards regression.
>
> Input is a single 2D form with samples as rows and clinical
> variables as columns. The operator reads a time column, an event
> column, and a set of covariate columns, then fits a Cox proportional
> hazards model.
>
> Statistics are delegated to lifelines.CoxPHFitter.
>
> Output form
> -----------
>     dims    = ["covariate", "statistic"]
>     labels  = {covariate: {name: i},
>                statistic: {"coef": 0, "HR": 1, "se": 2,
>                            "z": 3, "P": 4,
>                            "CI_low": 5, "CI_high": 6}}
>
> Categorical covariates
> ----------------------
> String-valued columns (or those encoded by a Reader) are expanded
> into one binary column per level, dropping the first level as the
> reference. The covariate label in the output is "{col}_{level}".
> Numeric columns pass through unchanged.
>
> Params:
>     time_label   : column with follow-up time (required)
>     event_label  : column with event indicator (required)
>     covariates   : list of column names to use as predictors
>                    (required)
>     categorical  : list of covariate names to treat as categorical;
>                    others are used as-is (optional)
>     weights_label: optional column with sample weights
>     output       : context key for the result (default: step name)
>
> Fit a Cox proportional hazards model.

## Inputs and outputs

Kind: `operator`. Operator ID: `cox_regression`.
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

Implementation: `src/task/step/steps/cox_regression.py` (`CoxRegressionStep`).
