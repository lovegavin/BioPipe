<!-- operon:generated -->
# PERMANOVA

## Purpose

> PERMANOVA — permutation-based multivariate analysis of variance.
>
> Given a distance matrix (produced by ``distance_matrix``) and a
> group label for each sample, tests whether the between-group
> distances are larger than expected by chance.
>
> Two inputs share a sample dim. The first is a square distance
> matrix, the second carries the group column. Both must have the
> same labels on the sample dim.
>
> Method
> ------
> Anderson (2001) PERMANOVA on a distance matrix:
>
>     a_ij    = d_ij^2 / 2
>     SS_T    = sum over all i,j of a_ij, divided by n
>     SS_W    = sum_g (1/n_g) * sum over i,j in g of a_ij
>     SS_A    = SS_T - SS_W
>     F       = (SS_A / (g-1)) / (SS_W / (n-g))
>     R^2     = SS_A / SS_T
>     p-value = fraction of permutations with F >= F_obs
>
> Two modes
> ---------
>     overall     one test across all groups (default)
>     pairwise    one test per unordered pair of groups, in addition
>                 to the overall test
>
> Output
> ------
>     dims    = ["comparison", "statistic"]
>     labels  = {comparison: {"overall": 0, "A vs B": 1, ...},
>                statistic: {"F": 0, "R2": 1, "P": 2, "n_perm": 3}}
>
> Params:
>     dist_dim        : sample dim on the distance matrix (default
>                       "sample")
>     group_dim       : sample dim on the metadata form (default
>                       same as dist_dim)
>     group_label     : column label on the metadata's other dim
>                       (required)
>     groups          : optional list of group names, in order; if
>                       omitted, all groups present in the metadata
>                       are used
>     pairwise        : run pairwise tests in addition to the overall
>                       test (default False)
>     n_permutations  : permutation count (default 999)
>     random_state    : random seed for permutations (default 0)
>     output          : context key for the result (default: step name)
>
> PERMANOVA on a distance matrix with a grouping column.

## Inputs and outputs

Kind: `operator`. Operator ID: `permanova`.
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

Implementation: `src/task/step/steps/permanova.py` (`PermanovaStep`).
