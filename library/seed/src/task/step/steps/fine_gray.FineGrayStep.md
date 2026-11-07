<!-- operon:generated -->
# Fine-Gray subdistribution regression

## Purpose

> Fine-Gray subdistribution hazard regression.
>
> The implementation follows the weighted partial-likelihood form of
> Fine and Gray (1999).  At each event time the risk set contains
> subjects still under observation plus subjects that already failed
> from a competing cause; the latter receive the time-dependent weight
> ``G(t) / G(T_i)`` where ``G`` is the Kaplan-Meier estimate of the
> censoring distribution.  Covariates are used without an intercept.
>
> Output form
> -----------
>     dims    = ["term", "statistic"]
>     labels  = {term: {name: i},
>                statistic: {"coef": 0, "HR": 1, "se": 2,
>                            "z": 3, "P": 4,
>                            "CI_low": 5, "CI_high": 6}}
>
> The reported standard errors use the robust sandwich estimator, matching
> ``cmprsk::crr`` (the ``var`` component), rather than the naive inverse
> information.
>
> Params:
>     time_label   : follow-up time column (required)
>     event_label  : event-code column (required)
>     covariates   : non-empty list of numeric covariate columns
>     event_code   : code for the event of interest (default 1)
>     censor_code  : code for administrative censoring (default 0)
>     confidence   : confidence level for coefficient intervals (default .95)
>     max_iter     : maximum Newton iterations (default 100)
>     output       : context key for the result (default: step name)

## Inputs and outputs

Kind: `operator`. Operator ID: `fine_gray`.
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

Implementation: `src/task/step/steps/fine_gray.py` (`FineGrayStep`).
