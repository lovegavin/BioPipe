<!-- operon:generated -->
# Moderated t differential analysis

## Purpose

> Two-group linear-model differential analysis with empirical Bayes.
>
> This is a limma-style workflow: per-feature group means and residual
> variances, variance shrinkage using an empirical-Bayes prior, moderated
> t statistics and BH correction. It is an independent Python
> implementation; it is not a byte-for-byte wrapper around R limma.
>
> The prior variance is estimated with the standard log-variance /
> trigamma moment approximation used by limma's ``fitFDist``. A balanced
> two-group design with ``prior_df: 0`` reduces to the ordinary pooled
> t-test, which is covered by a hand-calculated test.
>
> Output columns: logFC, mean_a, mean_b, t, P_VALUE, Q_VALUE,
> df_residual, df_prior.

## Inputs and outputs

Kind: `operator`. Operator ID: `limma_de`.
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

Implementation: `src/task/step/steps/limma_de.py` (`LimmaDeStep`).
