<!-- operon:generated -->
# Patterson's Fst

## Purpose

> Patterson's Fst estimator from biallelic genotype dosages.
>
> Estimates per-variant Fst with the unbiased F2 estimator of Patterson
> (2012, Appendix A), matching ``allel.patterson_fst``. Groups are selected
> from a metadata table, exactly like ``fst``. Variants with fewer than two
> called genotypes in either group get NaN statistics but keep their sample
> counts.
>
> The numerator is ``F2(A, B)``; the denominator adds the within-population
> heterozygosity estimators ``h_hat(A) + h_hat(B)``. Per-variant Fst can be
> negative and is not bounded to [0, 1].

## Inputs and outputs

Kind: `operator`. Operator ID: `patterson_fst`.
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

Implementation: `src/task/step/steps/patterson_fst.py` (`PattersonFstStep`).
