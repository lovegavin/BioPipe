<!-- operon:generated -->
# SIMPER

## Purpose

> SIMPER: similarity percentages between two groups.
>
> For samples i (group A) and j (group B) the Bray-Curtis
> dissimilarity is decomposed into per-taxon contributions
>
>     c_ij(k) = |x_ik - x_jk| / (sum_k x_ik + sum_k x_jk)
>
> and the operator reports, per taxon, the mean contribution over all
> cross-group pairs, the mean abundance in each group, the standard
> deviation and ratio of the contributions, and the cumulative
> contribution after sorting by decreasing average.
>
> The numbers match ``vegan::simper`` with ``permutations = 0`` for the
> ``average``, ``ava``, ``avb`` and ``cumsum`` columns.
>
> SIMPER decomposition of the Bray-Curtis dissimilarity.

## Inputs and outputs

Kind: `operator`. Operator ID: `simper`.
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

Implementation: `src/task/step/steps/simper.py` (`SimperStep`).
