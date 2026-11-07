<!-- operon:generated -->
# Conditional logistic regression

## Purpose

> Conditional logistic regression for matched case-control data.
>
> The conditional likelihood removes one intercept per stratum, so only
> within-stratum contrasts of the covariates are used.  The implementation
> uses Newton-Raphson on the exact conditional likelihood and the observed
> information for standard errors.
>
> Output form
> -----------
>     dims    = ["term", "statistic"]
>     labels  = {term: {covariate: i},
>                statistic: {"coef": 0, "se": 1, "z": 2, "P": 3,
>                            "CI_low": 4, "CI_high": 5, "OR": 6}}
>
> Params:
>     stratum_label : column identifying matched sets (required)
>     outcome_label : binary case/control column (required)
>     covariates    : non-empty list of numeric covariate columns
>     confidence    : confidence level for coefficient intervals (default .95)
>     max_iter      : maximum Newton iterations (default 100)
>     tol           : convergence tolerance on the Newton step (default 1e-8)
>     output        : context key for the result (default: step name)

## Inputs and outputs

Kind: `operator`. Operator ID: `conditional_logistic`.
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

Implementation: `src/task/step/steps/conditional_logistic.py` (`ConditionalLogisticStep`).
