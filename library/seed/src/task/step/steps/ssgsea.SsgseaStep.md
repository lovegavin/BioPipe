<!-- operon:generated -->
# ssGSEA

## Purpose

> Single-sample Gene Set Enrichment Analysis (ssGSEA).
>
> This follows the rank-based statistic used by GSVA's ``ssgsea`` method:
> for each sample, genes are ranked, a weighted rank-sum is compared with
> the expected rank-sum outside the set, and scores are normalized by the
> global range. It is a per-sample score, not the sample-level GSEA null.
>
> The implementation is independent of GSVA. ``tests/test_r_oracles.py``
> compares it with ``GSVA::gsva(ssgseaParam(...))`` when R/GSVA is present.

## Inputs and outputs

Kind: `operator`. Operator ID: `ssgsea`.
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

Implementation: `src/task/step/steps/ssgsea.py` (`SsgseaStep`).
