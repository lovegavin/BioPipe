<!-- operon:generated -->
# Signature score

## Purpose

> Per-cell signature scores using Scanpy's score_genes.
>
> The input gene sets are a binary [gene, gene_set] matrix, normally
> produced by GmtReader. For every set Scanpy's control-gene-corrected
> score is computed; genes absent from the expression matrix are skipped
> and reported. This is the standard scanpy/Seurat-style signature score,
> not a proprietary marker ranking.

## Inputs and outputs

Kind: `operator`. Operator ID: `marker_score`.
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

Implementation: `src/task/step/steps/marker_score.py` (`MarkerScoreStep`).
