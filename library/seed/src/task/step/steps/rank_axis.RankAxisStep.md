<!-- operon:generated -->
# Rank features

## Purpose

> Rank positions along one axis by a statistic and keep the top N.
>
> For each position along ``dim``, computes a ranking statistic over
> the other axes, then returns a subset of the input form containing
> only the selected positions.
>
> Selection
> ---------
> ``top_n``      keep the N highest-ranked positions
> ``min_value``  keep positions whose statistic is >= the threshold
>                (or <= when ``descending=False``)
>
> When both are given, the selection is their **intersection**: a
> position must be in the top N **and** satisfy the threshold.
>
> Ranking statistics
> ------------------
>     variance     variance across the other axes
>     std          standard deviation
>     mean         mean across the other axes
>     sum          sum across the other axes
>     nonzero      number of non-zero values
>     abs_mean     mean of absolute values
>     max          maximum value
>
> Missing cells are excluded from every statistic.
>
> Ties
> ----
> When several positions share the same statistic value, they are
> ordered by their original label order. If ``keep_ties`` is True and
> a tie straddles the top-N cutoff, all tied positions are kept and
> the result may exceed ``top_n``. If False (default), exactly
> ``top_n`` positions are kept.
>
> Params:
>     dim         : dimension to rank (required)
>     by          : statistic name (required)
>     top_n       : how many positions to keep
>     min_value   : threshold on the statistic
>     keep_ties   : keep all tied positions at the top-N cutoff
>                   (default False)
>     descending  : rank from largest to smallest (default True)
>     output      : context key for the result (default: step name)
>
> At least one of ``top_n`` or ``min_value`` is required.
>
> Rank positions along one axis by a statistic.

## Inputs and outputs

Kind: `operator`. Operator ID: `rank_axis`.
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

Implementation: `src/task/step/steps/rank_axis.py` (`RankAxisStep`).
