<!-- operon:generated -->
# 回归分析

## Purpose

> Multiple regression over one dimension of a wide form.
>
> Input is a single wide form. One position along a chosen dimension is
> the response; a set of other positions are covariates; all remaining
> positions are tested one at a time as predictors.
>
> For each predictor, the operator fits:
>
>     response ~ predictor + covariates
>
> Failure policy
> --------------
> A predictor is skipped, with a recorded reason, only when a known
> condition prevents a meaningful fit:
>
> * too few valid samples
> * predictor is constant
> * binary response has a single class in this subset
> * design matrix is rank-deficient
> * logistic fit hits perfect separation
> * the fit returned non-finite estimates
>
> Any other exception propagates. Nothing is silently swallowed.
>
> Regression of a response on each predictor, adjusting for covariates.
>
> Params:
>     dim        : dimension to iterate over
>     response   : label of the response column
>     covariates : labels of covariates (optional)
>     method     : "ols" | "logit" | "auto" (default)
>     output     : context key for the result

## Inputs and outputs

Kind: `operator`. Operator ID: `regress`.
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

Implementation: `src/task/step/steps/regress.py` (`RegressStep`).
