<!-- operon:generated -->
# Heterozygosity

## Purpose

> Observed and expected heterozygosity per variant.
>
> Computes, for diploid hard-call genotypes, the observed heterozygosity
> ``H_o = n_het / n_called``, the expected heterozygosity under HWE
> ``H_e = 2 p (1 - p)`` with ``p`` the alt allele frequency among called
> genotypes, and the inbreeding coefficient ``F_IS = 1 - H_o / H_e``.
> Matches ``allel.heterozygosity_observed`` and
> ``allel.heterozygosity_expected`` (ploidy 2). Variants with no called
> sample or with ``H_e = 0`` get NaN.

## Inputs and outputs

Kind: `operator`. Operator ID: `heterozygosity`.
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

Implementation: `src/task/step/steps/heterozygosity.py` (`HeterozygosityStep`).
