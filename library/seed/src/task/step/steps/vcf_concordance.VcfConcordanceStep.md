<!-- operon:generated -->
# vcf_concordance

## Purpose

> Genotype concordance between a query VCF and a truth VCF.
>
> Both inputs must be VCF/VCF.gz file artifacts.  One sample is compared per
> file (defaults to the first sample).  Records are compared per ALT allele:
> sites are keyed by (contig, position, ALT index, ALT base), so multi-allelic
> records are handled without normalising the files first.  REF/ALT identity is
> checked before genotypes are compared, so an allele mismatch is never silently
> counted as a genotype discordance.
>
> Output: 2D Form [metric, value].
>
> Compare one sample's genotypes between a query and a truth VCF.

## Inputs and outputs

Kind: `operator`. Operator ID: `vcf_concordance`.
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

Implementation: `src/task/step/steps/vcf_concordance.py` (`VcfConcordanceStep`).
