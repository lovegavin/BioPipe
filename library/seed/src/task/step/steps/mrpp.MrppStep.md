<!-- operon:generated -->
# MRPP

## Purpose

> MRPP: multi-response permutation procedure.
>
> Chance-corrected within-group agreement for community data
>
>     delta   = sum_g n_g * delta_g / n        (weight.type = 1)
>     E.delta = mean of all pairwise distances
>     A       = 1 - delta / E.delta
>
> with ``delta_g`` the mean within-group distance and ``n_g`` the group
> size. The p-value is the fraction of label permutations whose ``delta``
> is at most the observed value, matching ``vegan::mrpp`` including its
> add-one correction.
>
> Supported distances: euclidean, bray (Bray-Curtis) and manhattan.
>
> Multi-response permutation procedure with chance correction.

## Inputs and outputs

Kind: `operator`. Operator ID: `mrpp`.
Input count: `2`.
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

Implementation: `src/task/step/steps/mrpp.py` (`MrppStep`).
