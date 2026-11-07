<!-- operon:generated -->
# vcf_relatedness

## Purpose

> KING-robust kinship coefficients from a multi-sample VCF.
>
> The estimator is the KING-robust between-family formula (Manichaikul et al.
> 2010, Eq. 11), the same estimator used by plink2 `--make-king-table`:
>
>     phi_ij = 1/2 - (N_IBS1 + 4 N_IBS0) / (4 min(N_Aa(i), N_Aa(j)))
>
> over autosomal biallelic SNPs where both samples are called, with
> N_IBS1 = N_Aa(i) + N_Aa(j) - 2 N_Aa,Aa.  It is robust to population structure,
> so unrelated pairs centre near zero while duplicates and first-degree relatives
> move toward 0.5 and 0.25.
>
> Output: square 2D Form [sample, sample] (diagonal self-kinship 0.5).
>
> KING-robust kinship matrix for the selected VCF samples.

## Inputs and outputs

Kind: `operator`. Operator ID: `vcf_relatedness`.
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

Implementation: `src/task/step/steps/vcf_relatedness.py` (`VcfRelatednessStep`).
