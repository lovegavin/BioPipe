<!-- operon:generated -->
# Log-rank

## Purpose

> Log-rank test on survival data grouped by a label column.
>
> Compares survival distributions across groups. Statistics are
> delegated to lifelines:
>
>     multivariate_logrank_test   overall test across all groups
>     logrank_test                pairwise test between two groups
>
> Input is a single 2D form with samples as rows and clinical
> variables as columns.
>
> Output form
> -----------
>     dims    = ["comparison", "statistic"]
>     labels  = {comparison: {"overall": 0, "A vs B": 1, ...},
>                statistic: {"chi2": 0, "df": 1, "P": 2}}
>
> Params:
>     time_label   : follow-up time (required)
>     event_label  : event indicator, 1 = event, 0 = censored (required)
>     group_label  : group assignment (required)
>     group_map    : optional dict {raw: display} to remap group values
>     groups       : optional list of group names to keep, in order
>     pairwise     : also run pairwise comparisons (default False,
>                    only used when there are >= 3 groups)
>     output       : context key for the result (default: step name)
>
> Log-rank test for survival differences across groups.

## Inputs and outputs

Kind: `operator`. Operator ID: `logrank_test`.
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

Implementation: `src/task/step/steps/logrank_test.py` (`LogrankTestStep`).
