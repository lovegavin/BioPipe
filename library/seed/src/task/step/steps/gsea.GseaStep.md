<!-- operon:generated -->
# Preranked GSEA

## Purpose

> Preranked Gene Set Enrichment Analysis (GSEA).
>
> This is the classical weighted Kolmogorov-Smirnov enrichment score
> (Subramanian et al. 2005), followed by gene-set permutation p-values
> and BH correction. It is intentionally labelled *preranked*: it does
> not reorder samples or estimate per-sample phenotypes.
>
> Inputs
> ------
> ranked : [gene, statistic] with a ranking column (default log2FC)
> sets   : [gene, gene_set] binary membership
>
> The gene-set permutation null is the standard choice for preranked
> GSEA when sample-level expression is not available. The number of
> permutations is explicit and seeded; results are reproducible.
>
> This implementation is independent of fgsea/clusterProfiler. The test
> suite compares the enrichment-score calculation and null behavior.

## Inputs and outputs

Kind: `operator`. Operator ID: `gsea`.
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

Implementation: `src/task/step/steps/gsea.py` (`GseaStep`).
