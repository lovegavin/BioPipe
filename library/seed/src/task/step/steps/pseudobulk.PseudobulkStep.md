<!-- operon:generated -->
# Pseudobulk aggregation

## Purpose

> Aggregate single cells into sample/group-level pseudobulk profiles.
>
> This is the standard pseudobulk operation: cells are grouped by a
> metadata column, then summed or averaged per gene. It is deliberately
> separate from differential expression; downstream tests decide whether
> the pseudobulk matrix is used with limma/DESeq2 or descriptive plots.
>
> Shared genes are kept in the input order; cells absent from metadata
> are rejected rather than silently dropped.

## Inputs and outputs

Kind: `operator`. Operator ID: `pseudobulk`.
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

Implementation: `src/task/step/steps/pseudobulk.py` (`PseudobulkStep`).
