<!-- operon:generated -->
# Species accumulation

## Purpose

> Species accumulation curve with the exact (rarefaction) expectation.
>
> For each number of sites ``i`` the expected number of species is
>
>     richness(i) = sum_s (1 - C(n - freq_s, i) / C(n, i))
>
> where ``freq_s`` is the number of sites in which species ``s`` occurs
> and ``C`` is the binomial coefficient. The conditioned standard
> deviation follows ``vegan::specaccum(method = "exact", conditioned = TRUE)``:
>
>     var(i) = sum_s p_is (1 - p_is) + 2 * sum_{s < t} r_st sqrt(var_s var_t)
>
> with ``p_is`` the probability that species ``s`` is present in a random
> subset of ``i`` sites and ``r_st`` the correlation of the two presence
> indicators over all sites.
>
> The operator reads only the abundance table: a taxon counts as present
> when its value is greater than zero (``colSums(x > 0)``).
>
> Expected species richness as a function of the number of sites.

## Inputs and outputs

Kind: `operator`. Operator ID: `specaccum`.
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

Implementation: `src/task/step/steps/specaccum.py` (`SpecaccumStep`).
