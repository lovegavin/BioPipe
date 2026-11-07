<!-- operon:generated -->
# Polygenic risk score

## Purpose

> Polygenic risk score from aligned genotype dosages and variant weights.
>
> Inputs
> ------
> genotype : [variant, sample] allele dosage (0/1/2 or continuous dosage)
> weights  : [variant, statistic] with a beta-weight column
>
> The operator assumes the genotype dosage and weight are already aligned
> to the same effect allele. It deliberately does not guess strand or
> effect-allele orientation. Missing genotypes contribute zero and are
> counted in the export; the score is therefore a complete-case dosage
> sum over the variants present in both inputs.

## Inputs and outputs

Kind: `operator`. Operator ID: `prs`.
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

Implementation: `src/task/step/steps/prs.py` (`PrsStep`).
