<!-- operon:generated -->
# pileup_variants

## Purpose

> Call consensus variants from a BAM pileup against a reference FASTA.
>
> Inputs: BAM FileArtifact + FASTA FileArtifact.
> Output: VCF FileArtifact plus a summary report.
>
> The caller is deliberately simple and deterministic: a position becomes a
> variant when depth, base quality and alt-allele fraction clear the thresholds.
> It is not a replacement for a probabilistic variant caller.
>
> Call simple majority-allele variants from a BAM + reference FASTA.

## Inputs and outputs

Kind: `operator`. Operator ID: `pileup_variants`.
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

Implementation: `src/task/step/steps/pileup_variants.py` (`PileupVariantsStep`).
