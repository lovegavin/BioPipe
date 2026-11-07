<!-- operon:generated -->
# Pairwise alignment

## Purpose

> Global and local pairwise sequence alignment with affine gaps.
>
> The scoring convention follows Biopython's ``PairwiseAligner``: a gap of
> length ``k`` costs ``gap_open + (k - 1) * gap_extend``. Global alignment
> maximises the score over the full sequences; local alignment finds the
> best-scoring sub-alignment and reports it.
>
> Align exactly two sequences and report score and alignment counts.

## Inputs and outputs

Kind: `operator`. Operator ID: `pairwise_alignment`.
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

Implementation: `src/task/step/steps/pairwise_alignment.py` (`PairwiseAlignmentStep`).
